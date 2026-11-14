import asyncio
import logging
import sys

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    CallbackQuery,
    ErrorEvent,
    Message,
)
from pydantic import ValidationError

from bot.config import get_settings
from bot import nav, texts
from bot.db import (
    ROLE_ADMIN,
    close_db,
    ensure_member,
    fetchall,
    has_admin,
    init_db,
    promote_first_admin,
)
from bot.handlers.admin import router as admin_router
from bot.handlers.attachments import router as attachments_router
from bot.handlers.homework import router as homework_router
from bot.handlers.nav import router as nav_router
from bot.handlers.start import fallback_router, router as start_router
from bot.handlers.subjects import router as subjects_router

logger = logging.getLogger(__name__)

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}
CHAT_TYPES = {ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP}
_GROUP_ADMIN = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


def _should_promote(event: Message | CallbackQuery) -> bool:
    if isinstance(event, CallbackQuery):
        return True
    return bool(event.text and event.text.startswith("/"))


class RegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        chat = None
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery) and event.message is not None:
            chat = event.message.chat
        if user is None or user.is_bot or chat is None or chat.type not in CHAT_TYPES:
            data["role"] = None
            data["db_user"] = None
            data["internal_chat_id"] = None
            return await handler(event, data)
        if chat.type == ChatType.PRIVATE:
            member = await promote_first_admin(
                chat.id,
                user.id,
                user.username,
                group_admin=True,
            )
            data["db_user"] = member
            data["role"] = member["role"]
            data["internal_chat_id"] = member["chat_id"]
            return await handler(event, data)
        member = await ensure_member(chat.id, user.id, user.username)
        if member["role"] != ROLE_ADMIN and _should_promote(event):
            if not await has_admin(member["chat_id"]):
                member = await _promote_if_group_admin(event.bot, chat.id, user, member)
        data["db_user"] = member
        data["role"] = member["role"]
        data["internal_chat_id"] = member["chat_id"]
        return await handler(event, data)


async def _promote_if_group_admin(bot: Bot, chat_id: int, user, member):
    try:
        tg_member = await bot.get_chat_member(chat_id, user.id)
    except TelegramBadRequest:
        return member
    if tg_member.status not in _GROUP_ADMIN:
        return member
    return await promote_first_admin(
        chat_id,
        user.id,
        user.username,
        group_admin=True,
    )


async def run() -> None:
    try:
        settings = get_settings()
    except ValidationError:
        print("Укажи BOT_TOKEN в файле .env. Пример: bot/.env.example")
        raise SystemExit(1)
    await init_db(settings.database_path)
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage(), fsm_strategy=FSMStrategy.USER_IN_CHAT)
    dp.message.middleware(RegisterMiddleware())
    dp.callback_query.middleware(RegisterMiddleware())

    @dp.error()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception("update failed", exc_info=event.exception)
        callback = event.update.callback_query
        if callback is not None:
            try:
                await callback.answer()
            except TelegramBadRequest:
                return

    dp.include_router(nav_router)
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(subjects_router)
    dp.include_router(homework_router)
    dp.include_router(attachments_router)
    dp.include_router(fallback_router)
    logger.info("bot started, database: %s", settings.database_path)
    commands = [BotCommand(command="start", description="Меню")]
    await bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
    chats = await fetchall("SELECT telegram_chat_id FROM chats")
    for chat in chats:
        try:
            await bot.send_message(
                chat["telegram_chat_id"],
                texts.MAIN_MENU,
                reply_markup=nav.markup(nav.launcher_rows(), selective=False),
            )
        except TelegramBadRequest:
            logger.info("keyboard was not sent to chat %s", chat["telegram_chat_id"])
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await close_db()


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Нужен Python 3.11 или новее.")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
