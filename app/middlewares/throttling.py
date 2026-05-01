from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from app.config import get_settings


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._last_seen: dict[int, float] = {}
        self._last_cleanup: float = time.monotonic()
        self._cleanup_interval: float = 3600  # cleanup every hour
        self._entry_ttl: float = 86400  # remove entries older than 24 hours

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)
        
        now = time.monotonic()
        
        # Periodic cleanup to prevent memory leak
        if now - self._last_cleanup > self._cleanup_interval:
            expired_ids = [uid for uid, ts in self._last_seen.items() if now - ts > self._entry_ttl]
            for uid in expired_ids:
                del self._last_seen[uid]
            self._last_cleanup = now
        
        rate = get_settings().throttle_rate_seconds
        last = self._last_seen.get(tg_user.id, 0)
        if now - last < rate:
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Biroz sekinroq, iltimos.", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("⏳ Biroz sekinroq yozing, iltimos.")
            return None
        self._last_seen[tg_user.id] = now
        return await handler(event, data)
