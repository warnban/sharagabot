from aiogram import Router
from aiogram.enums import MessageEntityType
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import keyboards

from bot.callbacks import has_member
from bot.db import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_USER,
    get_user,
    get_user_by_username,
    is_admin,
    save_user,
    set_role,
    update_username,
)
from bot.handlers import TextCommand
from bot import texts

router = Router(name="admin")


def _head_end(text: str) -> int:
    parts = text.split(maxsplit=1)
    return len(parts[0]) if parts else 0


def target_from_message(message: Message, args: str) -> tuple[int | None, str | None]:
    text = message.text or ""
    head_end = _head_end(text)
    if message.entities:
        for entity in message.entities:
            if entity.offset < head_end:
                continue
            if entity.type == MessageEntityType.TEXT_MENTION and entity.user is not None:
                return entity.user.id, entity.user.username
            if entity.type == MessageEntityType.MENTION:
                value = text[entity.offset : entity.offset + entity.length]
                username = value[1:] if value.startswith("@") else value
                if username:
                    return None, username
    token = args.split(maxsplit=1)[0] if args else ""
    if token.startswith("@"):
        token = token[1:]
    token = token.strip()
    if not token:
        return None, None
    return None, token


async def _change_editor(
    message: Message,
    command_args: str,
    role: str | None,
    internal_chat_id: int | None,
    *,
    assign: bool,
) -> None:
    if not has_member(internal_chat_id, True) or internal_chat_id is None:
        await message.answer(texts.PRIVATE)
        return
    if not is_admin(role):
        await message.answer(texts.NO_ACCESS)
        return
    user_id, username = target_from_message(message, command_args)
    if user_id is None and not username:
        prompt = texts.SPECIFY_EDITOR if assign else texts.SPECIFY_REMOVE_EDITOR
        await message.answer(prompt)
        return
    me = await message.bot.me()
    if user_id == me.id or (
        username and me.username and username.casefold() == me.username.casefold()
    ):
        await message.answer(texts.USER_NOT_FOUND)
        return
    if user_id is not None:
        target = await get_user(internal_chat_id, user_id)
        if target is None:
            if not assign:
                await message.answer(texts.USER_NOT_FOUND)
                return
            await save_user(internal_chat_id, user_id, username, role=ROLE_EDITOR)
            await message.answer(texts.EDITOR_SET)
            return
        if username and username != target["username"]:
            await update_username(target["id"], username)
    else:
        target = await get_user_by_username(internal_chat_id, username or "")
        if target is None:
            await message.answer(texts.USER_NOT_FOUND)
            return
    if target["role"] == ROLE_ADMIN:
        await message.answer(texts.IS_ADMIN)
        return
    if assign:
        await set_role(target["id"], ROLE_EDITOR)
        await message.answer(texts.EDITOR_SET)
        return
    if target["role"] != ROLE_EDITOR:
        await message.answer(texts.NOT_EDITOR)
        return
    await set_role(target["id"], ROLE_USER)
    await message.answer(texts.EDITOR_REMOVED)


@router.message(TextCommand(texts.CMD_EDITOR))
async def cmd_editor(
    message: Message,
    command_args: str,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
) -> None:
    if not is_admin(role):
        await message.answer(texts.NO_ACCESS)
        return
    await keyboards.clear_step_keyboard(message.bot, message.chat.id, state)
    await state.clear()
    await _change_editor(
        message,
        command_args,
        role,
        internal_chat_id,
        assign=True,
    )


@router.message(TextCommand(texts.CMD_REMOVE_EDITOR))
async def cmd_remove_editor(
    message: Message,
    command_args: str,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
) -> None:
    if not is_admin(role):
        await message.answer(texts.NO_ACCESS)
        return
    await keyboards.clear_step_keyboard(message.bot, message.chat.id, state)
    await state.clear()
    await _change_editor(
        message,
        command_args,
        role,
        internal_chat_id,
        assign=False,
    )
