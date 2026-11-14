from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.callbacks import (
    AddFilesCB,
    ConfirmAttachCB,
    DeleteAttachCB,
    FilesCB,
    ListAttachCB,
    OpenAttachCB,
    answer_callback,
    has_member,
)
from bot.db import can_edit, user_lock
from bot.handlers import NotCommand
from bot.handlers.homework import render_card
from bot import keyboards, texts
from bot.services import attachments as files
from bot.services import homework as records

router = Router(name="attachments")


class AddFiles(StatesGroup):
    collecting = State()


def _is_command(message: Message) -> bool:
    return bool(message.text and message.text.startswith("/"))


async def _owns(state: FSMContext, user_id: int, chat_id: int) -> dict | None:
    data = await state.get_data()
    if data.get("user_id") != user_id or data.get("chat_id") != chat_id:
        return None
    return data


async def _show_attachment_list(
    bot,
    chat_id: int,
    internal_chat_id: int,
    record_id: int,
    role: str | None,
    kind: str,
    page: int,
    subject_page: int,
    message_id: int | None,
) -> None:
    record = await records.get_record(record_id, internal_chat_id)
    if record is None:
        await keyboards.edit_or_send(
            bot,
            chat_id,
            texts.RECORD_NOT_FOUND,
            keyboards.back_menu(),
            message_id,
        )
        return
    items = await files.list_attachments(record_id)
    await keyboards.edit_or_send(
        bot,
        chat_id,
        texts.attachment_list_text(items),
        keyboards.attachments_keyboard(
            items,
            role=role,
            record_id=record_id,
            kind=kind,
            page=page,
            subject_page=subject_page,
        ),
        message_id,
    )


@router.callback_query(OpenAttachCB.filter())
async def open_files(
    callback: CallbackQuery,
    callback_data: OpenAttachCB,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    record = await records.get_record(callback_data.record_id, internal_chat_id)
    if record is None:
        await answer_callback(callback, texts.RECORD_NOT_FOUND)
        return
    items = await files.list_attachments(record["id"])
    if not items:
        await answer_callback(callback, texts.NO_ATTACHMENTS)
        return
    await answer_callback(callback)
    chat_id = callback.message.chat.id
    anchor_id = callback.message.message_id
    await files.hide_opened(callback.bot, chat_id, anchor_id)
    sent = await files.send_attachments(
        callback.bot,
        chat_id,
        items,
        header=texts.attachment_header(record["subject_name"], record["date"]),
    )
    files.remember_opened(chat_id, anchor_id, sent)
    if not sent:
        await callback.message.answer(texts.SEND_FAILED)


@router.callback_query(ListAttachCB.filter())
async def list_files(
    callback: CallbackQuery,
    callback_data: ListAttachCB,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    await answer_callback(callback)
    await _show_attachment_list(
        callback.bot,
        callback.message.chat.id,
        internal_chat_id,
        callback_data.record_id,
        role,
        callback_data.k,
        callback_data.p,
        callback_data.sp,
        callback.message.message_id,
    )


@router.callback_query(DeleteAttachCB.filter())
async def ask_delete_file(
    callback: CallbackQuery,
    callback_data: DeleteAttachCB,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if not can_edit(role):
        await answer_callback(callback, texts.NO_ACCESS)
        return
    row = await files.get_attachment(callback_data.id, internal_chat_id)
    if row is None:
        await answer_callback(callback, texts.ATTACHMENT_NOT_FOUND)
        return
    position = await files.attachment_position(row["id"], row["record_id"])
    if position is None:
        await answer_callback(callback, texts.ATTACHMENT_NOT_FOUND)
        return
    index, total = position
    yes = ConfirmAttachCB(
        id=row["id"],
        y=1,
        k=callback_data.k,
        p=callback_data.p,
        sp=callback_data.sp,
    ).pack()
    no = ConfirmAttachCB(
        id=row["id"],
        y=0,
        k=callback_data.k,
        p=callback_data.p,
        sp=callback_data.sp,
    ).pack()
    await answer_callback(callback)
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        texts.confirm_delete_attachment(index, total),
        keyboards.confirm_keyboard(yes, no),
        callback.message.message_id,
    )


@router.callback_query(ConfirmAttachCB.filter())
async def confirm_delete_file(
    callback: CallbackQuery,
    callback_data: ConfirmAttachCB,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    row = await files.get_attachment(callback_data.id, internal_chat_id)
    if callback_data.y == 0:
        await answer_callback(callback)
        if row is None:
            await keyboards.edit_or_send(
                callback.bot,
                callback.message.chat.id,
                texts.ATTACHMENT_NOT_FOUND,
                keyboards.back_menu(),
                callback.message.message_id,
            )
            return
        await _show_attachment_list(
            callback.bot,
            callback.message.chat.id,
            internal_chat_id,
            row["record_id"],
            role,
            callback_data.k,
            callback_data.p,
            callback_data.sp,
            callback.message.message_id,
        )
        return
    if not can_edit(role):
        await answer_callback(callback, texts.NO_ACCESS)
        return
    if row is None:
        await answer_callback(callback, texts.ATTACHMENT_NOT_FOUND)
        return
    record_id = await files.delete_attachment(row["id"], internal_chat_id)
    await answer_callback(callback)
    if record_id is None:
        await keyboards.edit_or_send(
            callback.bot,
            callback.message.chat.id,
            texts.ATTACHMENT_NOT_FOUND,
            keyboards.back_menu(),
            callback.message.message_id,
        )
        return
    await _show_attachment_list(
        callback.bot,
        callback.message.chat.id,
        internal_chat_id,
        record_id,
        role,
        callback_data.k,
        callback_data.p,
        callback_data.sp,
        callback.message.message_id,
    )


@router.callback_query(AddFilesCB.filter())
async def start_add_files(
    callback: CallbackQuery,
    callback_data: AddFilesCB,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if not can_edit(role) or db_user is None or callback.from_user is None:
        await answer_callback(callback, texts.NO_ACCESS)
        return
    record = await records.get_record(callback_data.id, internal_chat_id)
    if record is None:
        await answer_callback(callback)
        await keyboards.edit_or_send(
            callback.bot,
            callback.message.chat.id,
            texts.RECORD_NOT_FOUND,
            keyboards.back_menu(),
            callback.message.message_id,
        )
        return
    await keyboards.clear_step_keyboard(callback.bot, callback.message.chat.id, state)
    await state.set_state(AddFiles.collecting)
    await state.set_data(
        {
            "chat_id": callback.message.chat.id,
            "user_id": callback.from_user.id,
            "internal_chat_id": internal_chat_id,
            "internal_user_id": db_user["id"],
            "record_id": record["id"],
            "kind": callback_data.k,
            "page": callback_data.p,
            "subject_page": callback_data.sp,
            "attachments": [],
            "bot_message_id": callback.message.message_id,
        }
    )
    await answer_callback(callback)
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        texts.ask_more_files_screen(record["subject_name"], record["kind"], record["date"]),
        keyboards.extra_files_keyboard(),
        callback.message.message_id,
    )


@router.callback_query(FilesCB.filter())
async def on_files_action(
    callback: CallbackQuery,
    callback_data: FilesCB,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    data = await _owns(state, callback.from_user.id, callback.message.chat.id)
    if await state.get_state() != AddFiles.collecting.state or data is None:
        await answer_callback(callback, texts.STALE)
        return
    if not can_edit(role) or db_user is None:
        await answer_callback(callback, texts.NO_ACCESS)
        await state.clear()
        return
    chat_id = callback.message.chat.id
    if callback_data.a == "cancel":
        await state.clear()
        await answer_callback(callback)
        await keyboards.edit_or_send(
            callback.bot,
            chat_id,
            texts.MAIN_MENU,
            keyboards.main_menu(role),
            callback.message.message_id,
        )
        return
    if callback_data.a != "done":
        await answer_callback(callback, texts.STALE)
        return
    async with user_lock(chat_id, callback.from_user.id):
        data = await _owns(state, callback.from_user.id, chat_id)
        if await state.get_state() != AddFiles.collecting.state or data is None or data.get("saving"):
            await answer_callback(callback, texts.STALE)
            return
        items = list(data.get("attachments") or [])
        if not items:
            await answer_callback(callback)
            await callback.message.answer(texts.NEED_FILE)
            return
        await state.update_data(saving=True)
        try:
            saved = await files.add_attachments(
                data["record_id"],
                internal_chat_id,
                db_user["id"],
                items,
            )
        except Exception:
            await state.update_data(saving=False)
            raise
        kind = data.get("kind") or texts.KIND_HW
        page = int(data.get("page") if data.get("page") is not None else -1)
        subject_page = int(data.get("subject_page") or 0)
        record_id = data["record_id"]
        message_id = data.get("bot_message_id")
        await state.clear()
    await answer_callback(callback)
    if not saved:
        await keyboards.edit_or_send(
            callback.bot,
            chat_id,
            texts.RECORD_NOT_FOUND,
            keyboards.back_menu(),
            message_id,
        )
        return
    rendered = await render_card(
        record_id,
        internal_chat_id,
        role,
        kind=kind,
        page=page,
        subject_page=subject_page,
    )
    if rendered is not None:
        text, markup = rendered
        await keyboards.edit_or_send(callback.bot, chat_id, text, markup, message_id)
    await callback.message.answer(texts.FILES_ADDED)


@router.message(AddFiles.collecting, F.photo)
@router.message(AddFiles.collecting, F.document)
async def collect_more(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    data = await _owns(state, message.from_user.id, message.chat.id)
    if data is None:
        return
    saved = await files.remember_file(state, message)
    if saved or not files.should_warn(message.chat.id, message.from_user.id, message.media_group_id):
        return
    await message.answer(texts.SEND_FILE)


@router.message(AddFiles.collecting, NotCommand())
async def more_other(message: Message) -> None:
    if _is_command(message) or message.from_user is None:
        return
    if not files.should_warn(message.chat.id, message.from_user.id, message.media_group_id):
        return
    await message.answer(texts.SEND_FILE)
