from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.callbacks import ConfirmSubjectCB, SubjectFormCB, answer_callback, has_member
from bot.db import is_admin
from bot.handlers import NotCommand, TextCommand
from bot import keyboards, nav, texts
from bot.services import subjects as subjects_db

router = Router(name="subjects")


class AddSubject(StatesGroup):
    name = State()


def _is_command(message: Message) -> bool:
    return bool(message.text and message.text.startswith("/"))


async def show_subject_names(
    bot,
    chat_id: int,
    internal_chat_id: int,
    message_id: int | None = None,
    role: str | None = None,
    state: FSMContext | None = None,
    reply_to: int | None = None,
) -> None:
    del message_id
    if state is None:
        return
    rows = await subjects_db.list_subjects(internal_chat_id)
    names = [row["name"] for row in rows]
    buttons = []
    if is_admin(role):
        buttons.append([nav.b(texts.BTN_ADD_SUBJECT, "new_subject", "success")])
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.subjects_message(names),
        buttons,
        reply_to=reply_to,
    )


async def begin_subject_prompt(
    bot,
    chat_id: int,
    user_id: int,
    internal_chat_id: int,
    internal_user_id: int,
    state: FSMContext,
    message_id: int | None = None,
    reply_to: int | None = None,
) -> None:
    del message_id
    old_id = (await state.get_data()).get("screen_message_id")
    await state.set_state(AddSubject.name)
    await state.set_data(
        {
            "screen_message_id": old_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "internal_chat_id": internal_chat_id,
            "internal_user_id": internal_user_id,
        }
    )
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.ASK_SUBJECT_NAME,
        [[nav.b(texts.BTN_CANCEL, "cancel")]],
        reply_to=reply_to,
    )


async def _create(message: Message, raw_name: str, internal_chat_id: int, user_id: int) -> str:
    status, name = texts.check_subject_name(raw_name)
    if status == "empty":
        return "empty"
    if status == "long":
        return "long"
    return await subjects_db.create_subject(internal_chat_id, name, user_id)


def _name_reply(status: str) -> str:
    if status == "empty":
        return texts.SUBJECT_NAME_REQUIRED
    if status == "long":
        return texts.SUBJECT_NAME_LONG
    if status == "exists":
        return texts.SUBJECT_EXISTS
    return texts.SUBJECT_ADDED


@router.message(TextCommand(texts.CMD_SUBJECTS))
async def cmd_subjects(
    message: Message,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await message.answer(texts.PRIVATE)
        return
    await keyboards.clear_step_keyboard(message.bot, message.chat.id, state)
    await state.clear()
    await show_subject_names(
        message.bot,
        message.chat.id,
        internal_chat_id,
        None,
        role,
        state,
        message.message_id,
    )


@router.message(TextCommand(texts.CMD_ADD_SUBJECT))
async def cmd_add_subject(
    message: Message,
    command_args: str,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if not has_member(internal_chat_id, db_user) or internal_chat_id is None or db_user is None:
        await message.answer(texts.PRIVATE)
        return
    if not is_admin(role):
        await message.answer(texts.NO_ACCESS)
        return
    if command_args.strip():
        if await state.get_state() is not None:
            await keyboards.clear_step_keyboard(message.bot, message.chat.id, state)
            await state.clear()
        status = await _create(message, command_args, internal_chat_id, db_user["id"])
        await message.answer(_name_reply(status))
        return
    if message.from_user is None:
        return
    await begin_subject_prompt(
        message.bot,
        message.chat.id,
        message.from_user.id,
        internal_chat_id,
        db_user["id"],
        state,
    )


@router.message(TextCommand(texts.CMD_DELETE_SUBJECT))
async def cmd_delete_subject(
    message: Message,
    command_args: str,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await message.answer(texts.PRIVATE)
        return
    if not is_admin(role):
        await message.answer(texts.NO_ACCESS)
        return
    await keyboards.clear_step_keyboard(message.bot, message.chat.id, state)
    await state.clear()
    status, name = texts.check_subject_name(command_args)
    if status == "empty":
        await message.answer(texts.SUBJECT_NAME_REQUIRED)
        return
    if status == "long":
        await message.answer(texts.SUBJECT_NAME_LONG)
        return
    subject = await subjects_db.find_subject(internal_chat_id, name)
    if subject is None:
        await message.answer(texts.SUBJECT_NOT_FOUND)
        return
    yes = ConfirmSubjectCB(id=subject["id"], y=1).pack()
    no = ConfirmSubjectCB(id=subject["id"], y=0).pack()
    await message.answer(
        texts.confirm_delete_subject(subject["name"]),
        reply_markup=keyboards.confirm_keyboard(yes, no),
    )


@router.callback_query(SubjectFormCB.filter())
async def cancel_subject_form(
    callback: CallbackQuery,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user):
        await answer_callback(callback, texts.STALE)
        return
    if await state.get_state() != AddSubject.name.state:
        await answer_callback(callback, texts.STALE)
        return
    data = await state.get_data()
    if data.get("user_id") != callback.from_user.id:
        await answer_callback(callback, texts.STALE)
        return
    await state.clear()
    await answer_callback(callback)
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        texts.MAIN_MENU,
        keyboards.main_menu(role),
        callback.message.message_id,
    )


@router.callback_query(ConfirmSubjectCB.filter())
async def confirm_subject(
    callback: CallbackQuery,
    callback_data: ConfirmSubjectCB,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if callback_data.y == 0:
        await answer_callback(callback)
        await keyboards.edit_or_send(
            callback.bot,
            callback.message.chat.id,
            texts.CANCELLED,
            keyboards.back_menu(),
            callback.message.message_id,
        )
        return
    if not is_admin(role):
        await answer_callback(callback, texts.NO_ACCESS)
        return
    deleted = await subjects_db.delete_subject(callback_data.id, internal_chat_id)
    await answer_callback(callback)
    text = texts.SUBJECT_DELETED if deleted else texts.SUBJECT_NOT_FOUND
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        text,
        keyboards.back_menu(),
        callback.message.message_id,
    )


@router.message(AddSubject.name, F.text, NotCommand())
async def subject_name(
    message: Message,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if _is_command(message):
        return
    if not is_admin(role) or internal_chat_id is None or db_user is None:
        await state.clear()
        await message.answer(texts.NO_ACCESS)
        return
    data = await state.get_data()
    if message.from_user is None or data.get("user_id") != message.from_user.id:
        return
    status = await _create(message, message.text or "", internal_chat_id, db_user["id"])
    if status != "ok":
        await message.answer(_name_reply(status))
        return
    await keyboards.clear_step_keyboard(message.bot, message.chat.id, state)
    await state.clear()
    await message.answer(texts.SUBJECT_ADDED)


@router.message(AddSubject.name, NotCommand())
async def subject_name_other(message: Message) -> None:
    if _is_command(message):
        return
    await message.answer(texts.ASK_SUBJECT_NAME)
