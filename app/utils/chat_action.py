from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.enums import ChatAction


async def keep_typing(bot: Bot, chat_id: int, stop_event: asyncio.Event, interval: float = 4.0) -> None:
    while not stop_event.is_set():
        with contextlib.suppress(Exception):
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def run_with_typing(bot: Bot, chat_id: int, operation: Callable[[], Awaitable[str]]) -> str:
    stop_event = asyncio.Event()
    task = asyncio.create_task(keep_typing(bot, chat_id, stop_event))
    try:
        return await operation()
    finally:
        stop_event.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
