import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaDocument, InputMediaPhoto, Message

from bot.db import execute, fetchall, fetchone, now_iso, transaction, user_lock

logger = logging.getLogger(__name__)

MEDIA_GROUP_LIMIT = 10
_seen_groups: list[tuple[int, int, str]] = []


def clean_items(items: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for item in items:
        file_id = item.get("file_id")
        file_type = item.get("file_type")
        if not file_id or file_type not in {"photo", "document"}:
            continue
        caption = item.get("caption") or None
        if isinstance(caption, str):
            caption = caption.strip()[:1024] or None
        file_name = item.get("file_name") or None
        cleaned.append(
            {
                "file_id": file_id,
                "file_type": file_type,
                "file_name": file_name,
                "caption": caption,
            }
        )
    return cleaned


def file_from_message(message: Message) -> dict | None:
    caption = (message.caption or "").strip()[:1024] or None
    if message.photo:
        return {
            "file_id": message.photo[-1].file_id,
            "file_type": "photo",
            "file_name": None,
            "caption": caption,
        }
    document = message.document
    if document is not None and document.file_id:
        return {
            "file_id": document.file_id,
            "file_type": "document",
            "file_name": document.file_name,
            "caption": caption,
        }
    return None


def count_types(items: list[dict]) -> tuple[int, int]:
    photos = 0
    documents = 0
    for item in items:
        if item.get("file_type") == "photo":
            photos += 1
        elif item.get("file_type") == "document":
            documents += 1
    return photos, documents


def group_for_send(items: list) -> list[tuple[str, list]]:
    photos = [item for item in items if item["file_type"] == "photo"]
    documents = [item for item in items if item["file_type"] == "document"]
    batches: list[tuple[str, list]] = []
    for kind, group in (("photo", photos), ("document", documents)):
        for offset in range(0, len(group), MEDIA_GROUP_LIMIT):
            batches.append((kind, group[offset : offset + MEDIA_GROUP_LIMIT]))
    return batches


def should_warn(chat_id: int, user_id: int, media_group_id: str | None) -> bool:
    if not media_group_id:
        return True
    key = (chat_id, user_id, media_group_id)
    if key in _seen_groups:
        return False
    _seen_groups.append(key)
    if len(_seen_groups) > 200:
        del _seen_groups[:100]
    return True


async def remember_file(state: FSMContext, message: Message) -> bool:
    item = file_from_message(message)
    if item is None or message.from_user is None:
        return False
    async with user_lock(message.chat.id, message.from_user.id):
        data = await state.get_data()
        items = list(data.get("attachments") or [])
        items.append(item)
        await state.update_data(attachments=items)
    return True


async def list_attachments(record_id: int) -> list:
    return await fetchall(
        "SELECT * FROM attachments WHERE record_id = ? ORDER BY id ASC",
        (record_id,),
    )


async def get_attachment(attachment_id: int, internal_chat_id: int):
    return await fetchone(
        """
        SELECT a.id, a.record_id, a.file_id, a.file_type, a.file_name, a.caption
        FROM attachments AS a
        JOIN records AS r ON r.id = a.record_id
        WHERE a.id = ? AND r.chat_id = ?
        """,
        (attachment_id, internal_chat_id),
    )


async def attachment_position(attachment_id: int, record_id: int) -> tuple[int, int] | None:
    rows = await list_attachments(record_id)
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        if row["id"] == attachment_id:
            return index, total
    return None


async def add_attachments(
    record_id: int,
    internal_chat_id: int,
    internal_user_id: int,
    items: list[dict],
) -> bool:
    prepared = clean_items(items)
    if not prepared:
        return False
    record = await fetchone(
        "SELECT id FROM records WHERE id = ? AND chat_id = ?",
        (record_id, internal_chat_id),
    )
    if record is None:
        return False
    created = now_iso()
    async with transaction():
        for item in prepared:
            await execute(
                """
                INSERT INTO attachments (
                    record_id, file_id, file_type, file_name, caption, uploaded_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    item["file_id"],
                    item["file_type"],
                    item.get("file_name"),
                    item.get("caption"),
                    internal_user_id,
                    created,
                ),
            )
        await execute(
            "UPDATE records SET updated_at = ? WHERE id = ?",
            (created, record_id),
        )
    return True


async def delete_attachment(attachment_id: int, internal_chat_id: int) -> int | None:
    row = await get_attachment(attachment_id, internal_chat_id)
    if row is None:
        return None
    async with transaction():
        await execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        await execute(
            "UPDATE records SET updated_at = ? WHERE id = ?",
            (now_iso(), row["record_id"]),
        )
    return row["record_id"]


_opened: dict[tuple[int, int], list[int]] = {}


def _caption(item) -> str | None:
    caption = item["caption"]
    if not caption:
        return None
    text = str(caption).strip()
    if not text:
        return None
    return text[:1024]


def _shown_caption(item, header: str | None, *, first: bool) -> str | None:
    own = _caption(item)
    if not first:
        return None
    if header and own:
        text = f"{header}\n\n{own}"
    else:
        text = header or own
    if not text:
        return None
    return text[:1024]


def _media(kind: str, batch: list, header: str | None):
    media = []
    for index, item in enumerate(batch):
        caption = _shown_caption(item, header, first=index == 0)
        if kind == "photo":
            media.append(InputMediaPhoto(media=item["file_id"], caption=caption))
        else:
            media.append(InputMediaDocument(media=item["file_id"], caption=caption))
    return media


async def _send_one(bot: Bot, chat_id: int, kind: str, item, caption: str | None) -> int | None:
    try:
        if kind == "photo":
            message = await bot.send_photo(chat_id, item["file_id"], caption=caption)
        else:
            message = await bot.send_document(chat_id, item["file_id"], caption=caption)
    except TelegramBadRequest:
        logger.warning("failed to send %s", kind)
        return None
    return message.message_id


async def _send_batch(bot: Bot, chat_id: int, kind: str, batch: list, header: str | None) -> list[int]:
    if len(batch) == 1:
        message_id = await _send_one(
            bot,
            chat_id,
            kind,
            batch[0],
            _shown_caption(batch[0], header, first=True),
        )
        return [message_id] if message_id else []
    try:
        messages = await bot.send_media_group(chat_id, media=_media(kind, batch, header))
        return [message.message_id for message in messages]
    except TelegramBadRequest:
        logger.info("media group was rejected, sending files separately")
    sent: list[int] = []
    for index, item in enumerate(batch):
        message_id = await _send_one(
            bot,
            chat_id,
            kind,
            item,
            _shown_caption(item, header, first=index == 0),
        )
        if message_id:
            sent.append(message_id)
    return sent


async def send_attachments(bot: Bot, chat_id: int, items: list, header: str | None = None) -> list[int]:
    # A media group holds 2-10 files of one type. Photos and documents are sent apart.
    sent: list[int] = []
    for kind, batch in group_for_send(items):
        sent.extend(await _send_batch(bot, chat_id, kind, batch, header))
    return sent


def remember_opened(chat_id: int, anchor_id: int, message_ids: list[int]) -> None:
    if message_ids:
        _opened[(chat_id, anchor_id)] = message_ids


async def hide_opened(bot: Bot, chat_id: int, anchor_id: int) -> None:
    message_ids = _opened.pop((chat_id, anchor_id), [])
    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id, message_id)
        except TelegramBadRequest:
            continue
