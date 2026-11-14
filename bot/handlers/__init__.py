from typing import Any

from aiogram import Bot
from aiogram.filters import Filter
from aiogram.types import Message


def split_command(text: str) -> tuple[str, str, str | None] | None:
    if not text or not text.startswith("/"):
        return None
    parts = text.split(maxsplit=1)
    token = parts[0][1:]
    rest = parts[1].strip() if len(parts) > 1 else ""
    if not token:
        return None
    mention = None
    if "@" in token:
        name, mention = token.split("@", 1)
        if not name or not mention:
            return None
    else:
        name = token
    return name.casefold(), rest, mention


class NotCommand(Filter):
    async def __call__(self, message: Message) -> bool:
        return not (message.text or "").startswith("/")


class TextCommand(Filter):
    def __init__(self, *names: str) -> None:
        self.names = {name.casefold() for name in names}

    async def __call__(self, message: Message, bot: Bot) -> bool | dict[str, Any]:
        parsed = split_command(message.text or "")
        if parsed is None:
            return False
        name, args, mention = parsed
        if name not in self.names:
            return False
        if mention is not None:
            me = await bot.me()
            if not me.username or mention.casefold() != me.username.casefold():
                return False
        return {"command_args": args}
