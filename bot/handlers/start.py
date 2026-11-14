from pathlib import Path

from aiogram import Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, FSInputFile, Message

from bot.callbacks import MenuCB, answer_callback, has_member
from bot.db import can_edit, is_admin, promote_first_admin
from bot.handlers import TextCommand
from bot.handlers.homework import begin_add, show_subjects
from bot.handlers.subjects import begin_subject_prompt, show_subject_names
from bot import keyboards, nav, texts

router = Router(name="start")
fallback_router = Router(name="fallback")
_AUTHOR_PHOTO = Path(__file__).resolve().parent.parent / "assets" / "author.jpg"
_CAPTION_LIMIT = 1024

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}
_JOINED = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.RESTRICTED,
}
_LEFT = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
_GROUP_ADMIN = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


@router.my_chat_member()
async def bot_added(event: ChatMemberUpdated, bot) -> None:
    if event.chat.type not in GROUP_TYPES:
        return
    me = await bot.me()
    if event.new_chat_member.user.id != me.id:
        return
    if event.old_chat_member.status not in _LEFT:
        return
    if event.new_chat_member.status not in _JOINED:
        return
    adder = event.from_user
    if adder is None or adder.is_bot:
        return
    group_admin = False
    try:
        member = await bot.get_chat_member(event.chat.id, adder.id)
        group_admin = member.status in _GROUP_ADMIN
    except TelegramBadRequest:
        group_admin = False
    await promote_first_admin(
        event.chat.id,
        adder.id,
        adder.username,
        group_admin=group_admin,
    )
    try:
        await bot.send_message(
            event.chat.id,
            texts.MAIN_MENU,
            reply_markup=nav.markup(nav.launcher_rows(), selective=False),
        )
    except TelegramBadRequest:
        return


async def send_about(bot, chat_id: int) -> None:
    text = texts.ABOUT_AUTHOR.strip()
    photo = FSInputFile(_AUTHOR_PHOTO)
    if len(text) <= _CAPTION_LIMIT:
        await bot.send_photo(chat_id, photo, caption=text)
        return
    cut = text.rfind("\n\n", 0, _CAPTION_LIMIT)
    if cut < 200:
        cut = _CAPTION_LIMIT
    await bot.send_photo(chat_id, photo, caption=text[:cut].strip())
    rest = text[cut:].strip()
    if rest:
        await bot.send_message(chat_id, rest)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if not has_member(internal_chat_id, db_user):
        await message.answer(texts.PRIVATE)
        return
    await nav.show_home(message.bot, message.chat.id, state, role, message.message_id)


@router.message(TextCommand(texts.CMD_HW))
async def cmd_hw(
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
    await show_subjects(
        message.bot,
        message.chat.id,
        internal_chat_id,
        0,
        None,
        role,
        state,
        message.message_id,
    )


@router.callback_query(MenuCB.filter())
async def on_menu(
    callback: CallbackQuery,
    callback_data: MenuCB,
    state: FSMContext,
    role: str | None,
    db_user,
    internal_chat_id: int | None,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user):
        await answer_callback(callback, texts.STALE if callback.message is None else texts.PRIVATE)
        return
    if internal_chat_id is None or db_user is None or callback.from_user is None:
        await answer_callback(callback, texts.STALE)
        return
    action = callback_data.a
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    if action == "about":
        await answer_callback(callback)
        await send_about(callback.bot, chat_id)
        return
    if action == "home":
        await answer_callback(callback)
        await nav.show_home(callback.bot, chat_id, state, role, None)
        return
    if action == "records":
        await keyboards.clear_step_keyboard(callback.bot, chat_id, state)
        await state.clear()
        await answer_callback(callback)
        await show_subjects(
            callback.bot, chat_id, internal_chat_id, 0, message_id, role, state
        )
        return
    if action == "add":
        if not can_edit(role):
            await answer_callback(callback, texts.NO_ACCESS)
            return
        await answer_callback(callback)
        await begin_add(
            callback.bot,
            chat_id,
            callback.from_user.id,
            internal_chat_id,
            db_user["id"],
            state,
            message_id,
            role,
        )
        return
    if action == "new_subject":
        if not is_admin(role):
            await answer_callback(callback, texts.NO_ACCESS)
            return
        await answer_callback(callback)
        await begin_subject_prompt(
            callback.bot,
            chat_id,
            callback.from_user.id,
            internal_chat_id,
            db_user["id"],
            state,
            message_id,
        )
        return
    if action == "subjects":
        await keyboards.clear_step_keyboard(callback.bot, chat_id, state)
        await state.clear()
        await answer_callback(callback)
        await show_subject_names(
            callback.bot, chat_id, internal_chat_id, message_id, role, state
        )
        return
    await answer_callback(callback, texts.STALE)


@fallback_router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    await answer_callback(callback, texts.STALE)
