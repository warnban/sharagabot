from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyParameters

from bot.db import can_edit, is_admin
from bot.services import attachments as files
from bot import texts


def b(text: str, action: str, style: str | None = None, **payload) -> dict:
    item = {"t": text, "a": action}
    if style:
        item["style"] = style
    for key, value in payload.items():
        if value is not None:
            item[key] = value
    return item


def home_rows(role: str | None) -> list[list[dict]]:
    rows = [[b(texts.BTN_RECORDS, "records")]]
    if can_edit(role):
        rows.append([b(texts.BTN_ADD, "add", "success")])
    rows.append([b(texts.BTN_SUBJECTS, "subjects")])
    return rows


def launcher_rows() -> list[list[dict]]:
    return [
        [b(texts.BTN_RECORDS, "records")],
        [b(texts.BTN_ADD, "add", "success")],
        [b(texts.BTN_SUBJECTS, "subjects")],
    ]


def rows_kind() -> list[list[dict]]:
    return [
        [b(texts.BTN_HW, "kind", kind="dz"), b(texts.BTN_NOTE, "kind", kind="note")],
        [b(texts.BTN_CANCEL, "cancel")],
    ]


def rows_date(*, entering: bool) -> list[list[dict]]:
    rows = [[
        b(texts.BTN_TODAY, "date", days=0),
        b(texts.BTN_TOMORROW, "date", days=1),
    ]]
    if not entering:
        rows.append([b(texts.BTN_ENTER_DATE, "enter_date")])
    rows.append([b(texts.BTN_CANCEL, "cancel")])
    return rows


def rows_text() -> list[list[dict]]:
    return [[b(texts.BTN_CANCEL, "cancel")]]


def rows_files(*, extra: bool = False) -> list[list[dict]]:
    rows = [[b(texts.BTN_DONE, "done", "success")]]
    if not extra:
        rows.append([b(texts.BTN_NO_FILES, "no_files")])
    rows.append([b(texts.BTN_CANCEL, "cancel")])
    return rows


def rows_preview() -> list[list[dict]]:
    return [
        [b(texts.BTN_PUBLISH, "publish", "success")],
        [b(texts.BTN_CANCEL, "cancel")],
    ]


def markup(rows: list[list[dict]], *, selective: bool = True) -> ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]] = []
    for row in rows:
        keyboard.append(
            [
                KeyboardButton(text=item["t"], **({"style": item["style"]} if item.get("style") else {}))
                for item in row
            ]
        )
    keyboard.append(
        [
            KeyboardButton(text=texts.BTN_HOME),
            KeyboardButton(text=texts.BTN_ABOUT, style="primary"),
        ]
    )
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        selective=selective,
    )


def _unique(rows: list[list[dict]]) -> list[dict]:
    seen: set[str] = set()
    flat: list[dict] = []
    for row in rows:
        for item in row:
            base = item["t"]
            number = 2
            while item["t"] in seen:
                item["t"] = f"{base} ({number})"
                number += 1
            seen.add(item["t"])
            flat.append(item)
    return flat


async def show_screen(
    bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    rows: list[list[dict]],
    *,
    reply_to: int | None = None,
) -> int | None:
    data = await state.get_data()
    old_id = data.get("screen_message_id")
    flat = _unique(rows)
    keyboard = markup(rows)
    sent = None
    if reply_to:
        try:
            sent = await bot.send_message(
                chat_id,
                texts.clip(text),
                reply_markup=keyboard,
                reply_parameters=ReplyParameters(
                    message_id=reply_to,
                    allow_sending_without_reply=True,
                ),
            )
        except TelegramBadRequest:
            sent = None
    if sent is None:
        try:
            sent = await bot.send_message(chat_id, texts.clip(text), reply_markup=keyboard)
        except TelegramBadRequest:
            return old_id
    if old_id and old_id != sent.message_id:
        await files.hide_opened(bot, chat_id, old_id)
        try:
            await bot.delete_message(chat_id, old_id)
        except TelegramBadRequest:
            pass
    await state.update_data(nav=flat, screen_message_id=sent.message_id)
    return sent.message_id


async def show_home(bot, chat_id: int, state: FSMContext, role: str | None, reply_to: int | None) -> None:
    data = await state.get_data()
    old_id = data.get("screen_message_id")
    await state.set_state(None)
    await state.set_data({"screen_message_id": old_id})
    await show_screen(bot, chat_id, state, texts.MAIN_MENU, home_rows(role), reply_to=reply_to)
