from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import get_settings
from app.middlewares.throttling import ThrottlingMiddleware
from app.middlewares.user_middleware import UserMiddleware


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    settings = get_settings()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(ThrottlingMiddleware())
    dp.update.middleware(UserMiddleware())
    return bot, dp
