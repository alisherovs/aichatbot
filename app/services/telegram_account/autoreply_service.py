from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from app.database.models import AutoreplyLog, User
from app.database.repositories import TelegramAccountRepository
from app.database.session import async_session_maker
from app.services.ai.ai_service import AIServiceError, generate_autoreply_response
from app.services.usage_service import can_use_ai, consume_ai_credit, get_plan_limit

logger = logging.getLogger(__name__)

INTRO_TEXT = "Assalomu alaykum! Hozir sizga AI yordamchi javob beradi. Savolingizni yozing, imkon qadar aniq va foydali javob beraman."
FAILED_TEXT = "Hozir javob tayyorlashda muammo bo‘ldi. Birozdan keyin qayta yozib ko‘ring."
MIN_REPLY_INTERVAL_SECONDS = 5
COMBINE_WINDOW_SECONDS = 1.2

_queues: dict[tuple[int, int], asyncio.Queue["IncomingPrivateMessage"]] = {}
_workers: dict[tuple[int, int], asyncio.Task] = {}
_locks: dict[tuple[int, int], asyncio.Lock] = {}


@dataclass
class IncomingPrivateMessage:
    user_id: int
    peer_id: int
    peer_name: str | None
    text: str
    event_id: int | None = None


def draft_keyboard(log_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yuborish", callback_data=f"draft:send:{log_id}"),
                InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"draft:edit:{log_id}"),
            ],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"draft:cancel:{log_id}")],
        ]
    )


async def enqueue_incoming_message(bot: Bot, client: TelegramClient, message: IncomingPrivateMessage) -> None:
    key = (message.user_id, message.peer_id)
    queue = _queues.setdefault(key, asyncio.Queue())
    await queue.put(message)
    worker = _workers.get(key)
    if worker is None or worker.done():
        _workers[key] = asyncio.create_task(_process_peer_queue(bot, client, key))


async def _process_peer_queue(bot: Bot, client: TelegramClient, key: tuple[int, int]) -> None:
    queue = _queues[key]
    lock = _locks.setdefault(key, asyncio.Lock())
    while True:
        try:
            first = await asyncio.wait_for(queue.get(), timeout=300)
        except asyncio.TimeoutError:
            _queues.pop(key, None)
            _workers.pop(key, None)
            _locks.pop(key, None)
            return

        batch = [first]
        await asyncio.sleep(COMBINE_WINDOW_SECONDS)
        while not queue.empty():
            batch.append(queue.get_nowait())

        async with lock:
            try:
                await process_incoming_batch(bot, client, batch)
            except Exception:
                logger.exception("Autoreply batch failed user_id=%s peer_id=%s", key[0], key[1])
            finally:
                for _ in batch:
                    queue.task_done()


async def log_autoreply(
    user_id: int,
    peer_id: int,
    peer_name: str | None,
    incoming_text: str,
    ai_reply: str | None,
    status: str,
    skipped_reason: str | None = None,
    provider: str | None = None,
    error_text: str | None = None,
) -> int:
    async with async_session_maker() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        item = await TelegramAccountRepository(session).log_autoreply(
            user_id=user_id,
            peer_id=peer_id,
            peer_name=peer_name,
            incoming_text=(incoming_text or "")[:4000],
            ai_reply=ai_reply[:4000] if ai_reply else None,
            status=status,
            skipped_reason=skipped_reason,
            provider=provider,
            error_text=error_text[:1000] if error_text else None,
            persona_key=user.selected_persona if user else None,
        )
        await session.commit()
        logger.info(
            "Autoreply log user_id=%s peer_id=%s status=%s reason=%s provider=%s",
            user_id,
            peer_id,
            status,
            skipped_reason,
            provider,
        )
        return item.id


async def process_incoming_batch(bot: Bot, client: TelegramClient, messages: list[IncomingPrivateMessage]) -> None:
    latest = messages[-1]
    text = "\n".join(m.text.strip() for m in messages if m.text and m.text.strip()).strip()
    if not text:
        await log_autoreply(latest.user_id, latest.peer_id, latest.peer_name, "", None, "skipped", "skipped_empty_text")
        return

    snapshot = await _load_runtime_snapshot(latest.user_id, latest.peer_id, latest.peer_name)
    if snapshot is False:
        return
    if snapshot is None:
        await log_autoreply(latest.user_id, latest.peer_id, latest.peer_name, text, None, "skipped", "skipped_user_missing")
        return

    user, mode, enabled, intro_sent, last_reply_at, cooldown_until, delay_seconds, notify_owner, daily_limit, used_today = snapshot

    if not enabled or mode == "off":
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, None, "skipped", "skipped_disabled")
        return
    if cooldown_until and cooldown_until > datetime.utcnow():
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, None, "skipped", "skipped_cooldown")
        return

    if not intro_sent:
        sent = await _send_intro(client, latest)
        if not sent:
            return
        if mode == "assistant_only":
            await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, INTRO_TEXT, "sent", provider="intro")
            return

    if mode == "assistant_only":
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, None, "skipped", "skipped_assistant_only")
        return

    if used_today >= daily_limit:
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, None, "skipped", "skipped_limit")
        return

    if last_reply_at:
        elapsed = (datetime.utcnow() - last_reply_at).total_seconds()
        if elapsed < MIN_REPLY_INTERVAL_SECONDS:
            await asyncio.sleep(MIN_REPLY_INTERVAL_SECONDS - elapsed)

    if not await _can_use_ai_now(user.id):
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, None, "skipped", "skipped_limit")
        return

    try:
        reply = await _generate_with_peer_typing(client, user.id, latest.peer_id, text)
    except AIServiceError as exc:
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, None, "failed", "failed_ai", "groq", str(exc))
        try:
            await client.send_message(latest.peer_id, FAILED_TEXT)
        except Exception:
            logger.exception("Could not send failure text user_id=%s peer_id=%s", user.id, latest.peer_id)
        return
    except Exception as exc:
        logger.exception("Autoreply AI generation failed user_id=%s peer_id=%s", user.id, latest.peer_id)
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, None, "failed", "failed_ai", "groq", str(exc))
        return

    log_id = await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, reply, "pending", provider="groq")
    if mode == "confirm":
        await notify_draft(bot, user.id, latest.peer_name, text, reply, log_id)
        return

    if delay_seconds:
        await asyncio.sleep(delay_seconds)
    try:
        await client.send_message(latest.peer_id, reply)
    except FloodWaitError as exc:
        await _set_cooldown(user.id, latest.peer_id, exc.seconds)
        await _mark_log_failed(log_id, f"FloodWait: {exc.seconds}")
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, reply, "failed", "failed_send", "groq", f"FloodWait: {exc.seconds}")
        return
    except Exception as exc:
        await _mark_log_failed(log_id, str(exc))
        await log_autoreply(user.id, latest.peer_id, latest.peer_name, text, reply, "failed", "failed_send", "groq", str(exc))
        return

    await _mark_success(user.id, latest.peer_id, log_id)
    if notify_owner:
        await notify_owner_reply(bot, user.id, latest.peer_name, text, reply)


async def _load_runtime_snapshot(user_id: int, peer_id: int, peer_name: str | None):
    async with async_session_maker() as session:
        repo = TelegramAccountRepository(session)
        user = await session.scalar(select(User).where(User.id == user_id))
        if user is None:
            return False
        settings = await repo.get_settings(user_id)
        await repo.reset_autoreply_usage_if_needed(settings)
        chat_state = await repo.mark_incoming(user_id, peer_id, peer_name)

        if await repo.is_blocked(user_id, peer_id):
            await session.commit()
            await log_autoreply(user_id, peer_id, peer_name, "", None, "skipped", "skipped_blocked")
            return False
        allowed_count = await repo.allowed_count(user_id)
        if allowed_count and not await repo.is_allowed(user_id, peer_id):
            await session.commit()
            await log_autoreply(user_id, peer_id, peer_name, "", None, "skipped", "skipped_not_allowed")
            return None
        if settings.reply_only_when_away and chat_state.last_owner_outgoing_at:
            away_after = timedelta(minutes=settings.away_after_minutes or 5)
            if datetime.utcnow() - chat_state.last_owner_outgoing_at < away_after:
                await session.commit()
                await log_autoreply(user_id, peer_id, peer_name, "", None, "skipped", "skipped_away_rule")
                return False

        daily_limit = get_plan_limit(user.plan)
        settings.daily_reply_limit = daily_limit
        snapshot = (
            user,
            settings.mode,
            settings.enabled,
            chat_state.intro_sent,
            chat_state.last_reply_at,
            chat_state.cooldown_until,
            max(0, settings.delay_seconds or 0),
            bool(settings.notify_owner_on_reply),
            daily_limit,
            int(settings.used_today or 0),
        )
        await session.commit()
        return snapshot


async def _send_intro(client: TelegramClient, message: IncomingPrivateMessage) -> bool:
    try:
        await client.send_message(message.peer_id, INTRO_TEXT)
        async with async_session_maker() as session:
            repo = TelegramAccountRepository(session)
            await repo.mark_intro_sent(message.user_id, message.peer_id)
            await repo.mark_reply_sent(message.user_id, message.peer_id)
            await session.commit()
        return True
    except FloodWaitError as exc:
        await _set_cooldown(message.user_id, message.peer_id, exc.seconds)
        await log_autoreply(message.user_id, message.peer_id, message.peer_name, message.text, None, "failed", "failed_send", "intro", f"FloodWait: {exc.seconds}")
        return False
    except Exception as exc:
        await log_autoreply(message.user_id, message.peer_id, message.peer_name, message.text, None, "failed", "failed_send", "intro", str(exc))
        return False


async def generate_ai_reply(user_id: int, peer_id: int, text: str) -> str:
    async with async_session_maker() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if user is None:
            raise ValueError("Foydalanuvchi topilmadi.")
        recent_rows = await session.execute(
            select(AutoreplyLog)
            .where(AutoreplyLog.user_id == user_id, AutoreplyLog.peer_id == peer_id)
            .order_by(AutoreplyLog.created_at.desc())
            .limit(5)
        )
        recent = list(reversed(recent_rows.scalars().all()))
        context: list[dict[str, str]] = []
        for row in recent:
            context.append({"role": "user", "content": row.incoming_text[:300]})
            if row.ai_reply:
                context.append({"role": "assistant", "content": row.ai_reply[:300]})
    logger.debug(
        "Generating Groq autoreply user_id=%s peer_id=%s persona=%s",
        user_id,
        peer_id,
        user.selected_persona if user else None,
    )
    return await generate_autoreply_response(user, text, context=context)


async def _generate_with_peer_typing(client: TelegramClient, user_id: int, peer_id: int, text: str) -> str:
    action = client.action(peer_id, "typing")
    try:
        await action.__aenter__()
    except Exception:
        return await generate_ai_reply(user_id, peer_id, text)
    try:
        return await generate_ai_reply(user_id, peer_id, text)
    finally:
        with contextlib.suppress(Exception):
            await action.__aexit__(None, None, None)


async def _can_use_ai_now(user_id: int) -> bool:
    async with async_session_maker() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if user is None:
            return False
        ok = can_use_ai(user)
        await session.commit()
        return ok


async def _mark_success(user_id: int, peer_id: int, log_id: int) -> None:
    async with async_session_maker() as session:
        repo = TelegramAccountRepository(session)
        await repo.update_log_status(log_id, "sent")
        await repo.mark_reply_sent(user_id, peer_id)
        settings = await repo.get_settings(user_id)
        await repo.consume_autoreply_credit(settings)
        user = await session.scalar(select(User).where(User.id == user_id))
        if user:
            consume_ai_credit(user)
        await session.commit()


async def notify_draft(bot: Bot, user_id: int, peer_name: str | None, incoming: str, reply: str, log_id: int) -> None:
    chat_id = await _owner_bot_chat_id(user_id)
    await bot.send_message(
        chat_id,
        "<b>✍️ AI javob loyihasi</b>\n\n"
        f"Kimdan: <b>{peer_name or 'Noma’lum'}</b>\n"
        f"Xabar: {incoming}\n\n"
        f"Javob: {reply}",
        reply_markup=draft_keyboard(log_id),
    )


async def notify_owner_reply(bot: Bot, user_id: int, peer_name: str | None, incoming: str, reply: str) -> None:
    chat_id = await _owner_bot_chat_id(user_id)
    await bot.send_message(
        chat_id,
        "<b>🤖 AI javob berdi</b>\n\n"
        f"Kimdan: <b>{peer_name or 'Noma’lum'}</b>\n"
        f"Xabar: {incoming}\n"
        f"Javob: {reply}",
    )


async def _owner_bot_chat_id(user_id: int) -> int:
    async with async_session_maker() as session:
        owner = await session.scalar(select(User).where(User.id == user_id))
        return owner.telegram_id if owner else user_id


async def _set_cooldown(user_id: int, peer_id: int, seconds: int) -> None:
    async with async_session_maker() as session:
        state = await TelegramAccountRepository(session).get_chat_state(user_id, peer_id)
        state.cooldown_until = datetime.utcnow() + timedelta(seconds=seconds)
        await session.commit()


async def _mark_log_failed(log_id: int, error_text: str) -> None:
    async with async_session_maker() as session:
        repo = TelegramAccountRepository(session)
        await repo.update_log_status(log_id, "failed")
        log = await repo.get_log(log_id)
        if log:
            log.error_text = error_text[:1000]
        await session.commit()
