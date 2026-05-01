from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


def is_message_not_modified_error(error: Exception) -> bool:
    return isinstance(error, TelegramBadRequest) and "message is not modified" in str(error).lower()


async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as exc:
        if is_message_not_modified_error(exc):
            return
        raise
