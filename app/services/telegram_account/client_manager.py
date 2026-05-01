from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from sqlalchemy import select
from telethon import TelegramClient, events
from telethon.errors import AuthKeyError, FloodWaitError
from telethon.sessions import StringSession

from app.config import get_settings
from app.database.models import TelegramSession, User
from app.database.repositories import LinkedGroupRepository, TelegramAccountRepository
from app.database.session import async_session_maker
from app.services.telegram_account.autoreply_service import (
    IncomingPrivateMessage,
    enqueue_incoming_message,
    generate_ai_reply,
    log_autoreply,
    notify_owner_reply,
)
from app.services.telegram_account.session_service import decrypt_session
from app.services.usage_service import can_use_ai, consume_ai_credit

logger = logging.getLogger(__name__)
active_clients: dict[int, TelegramClient] = {}
_tasks: dict[int, asyncio.Task] = {}
_schedule_tasks: dict[int, asyncio.Task] = {}
_bot: Bot | None = None


def configure_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


async def create_client_from_session(user_id: int) -> TelegramClient:
    settings = get_settings()
    if not settings.telegram_api_id_int or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID yoki TELEGRAM_API_HASH sozlanmagan.")
    async with async_session_maker() as session:
        account = await TelegramAccountRepository(session).get_session(user_id)
        if account is None or not account.is_active:
            raise RuntimeError("Telegram session topilmadi yoki faol emas.")
        session_string = decrypt_session(account.encrypted_session)
    return TelegramClient(StringSession(session_string), settings.telegram_api_id_int, settings.telegram_api_hash)


async def start_user_client(user_id: int, bot: Bot | None = None) -> None:
    if bot is not None:
        configure_bot(bot)
    if _bot is None:
        raise RuntimeError("Bot instance sozlanmagan.")
    task = _tasks.get(user_id)
    if task and not task.done():
        return
    
    # Wrap the supervisor in a cleanup task
    async def _supervised_client() -> None:
        try:
            await _client_supervisor(user_id)
        except asyncio.CancelledError:
            logger.info("Client supervisor cancelled for user %s", user_id)
            raise
        except Exception:
            logger.exception("Client supervisor failed for user %s", user_id)
        finally:
            # Ensure cleanup
            _tasks.pop(user_id, None)
            active_clients.pop(user_id, None)
    
    _tasks[user_id] = asyncio.create_task(_supervised_client())


async def start_enabled_clients(bot: Bot) -> None:
    configure_bot(bot)
    async with async_session_maker() as session:
        result = await session.execute(
            select(TelegramSession.user_id).where(TelegramSession.is_active.is_(True))
        )
        user_ids = list(result.scalars().all())
    for user_id in user_ids:
        await start_user_client(user_id, bot)


async def stop_user_client(user_id: int) -> None:
    task = _tasks.pop(user_id, None)
    if task:
        task.cancel()
    schedule_task = _schedule_tasks.pop(user_id, None)
    if schedule_task:
        schedule_task.cancel()
    client = active_clients.pop(user_id, None)
    if client:
        await client.disconnect()


async def send_manual_reply(user_id: int, chat_id: int, text: str) -> None:
    client = active_clients.get(user_id)
    temporary = False
    if client is None:
        client = await create_client_from_session(user_id)
        await client.connect()
        temporary = True
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session muddati tugagan. Accountni qayta ulang.")
        await client.send_message(chat_id, text)
        async with async_session_maker() as session:
            await TelegramAccountRepository(session).mark_reply_sent(user_id, chat_id)
            await session.commit()
    finally:
        if temporary:
            await client.disconnect()


async def list_user_groups(user_id: int, limit: int = 100) -> list[dict]:
    client = active_clients.get(user_id)
    temporary = False
    if client is None:
        client = await create_client_from_session(user_id)
        await client.connect()
        temporary = True
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session muddati tugagan. Accountni qayta ulang.")
        groups: list[dict] = []
        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            is_group = bool(getattr(dialog, "is_group", False) or getattr(entity, "megagroup", False))
            if not is_group:
                continue
            groups.append(
                {
                    "id": int(dialog.id),
                    "title": dialog.name or getattr(entity, "title", None) or str(dialog.id),
                    "username": getattr(entity, "username", None),
                }
            )
        return groups
    finally:
        if temporary:
            await client.disconnect()


async def _client_supervisor(user_id: int) -> None:
    backoff = 1
    while True:
        client: TelegramClient | None = None
        try:
            client = await create_client_from_session(user_id)
            _register_handlers(client, user_id)
            await client.connect()
            if not await client.is_user_authorized():
                raise AuthKeyError("Session is not authorized")
            active_clients[user_id] = client
            _start_schedule_worker(user_id, client)
            backoff = 1
            logger.info("Telethon client started for user %s", user_id)
            await client.run_until_disconnected()
            logger.warning("Telethon client disconnected for user %s", user_id)
        except asyncio.CancelledError:
            if client:
                await client.disconnect()
            raise
        except AuthKeyError:
            logger.warning("Telegram session expired for user %s", user_id)
            await _disable_settings(user_id)
            return
        except Exception:
            logger.exception("Telethon client failed for user %s", user_id)
        finally:
            if active_clients.get(user_id) is client:
                active_clients.pop(user_id, None)
            schedule_task = _schedule_tasks.pop(user_id, None)
            if schedule_task:
                schedule_task.cancel()
            if client:
                await client.disconnect()
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


def _register_handlers(client: TelegramClient, user_id: int) -> None:
    @client.on(events.NewMessage(incoming=True))
    async def on_incoming(event):
        try:
            peer_id_for_log = int(event.chat_id or 0)
            logger.info(
                "Incoming event user_id=%s peer_id=%s event_id=%s out=%s private=%s text_len=%s",
                user_id,
                peer_id_for_log,
                getattr(event, "id", None),
                event.out,
                event.is_private,
                len(event.raw_text or ""),
            )
            if event.out:
                await log_autoreply(user_id, peer_id_for_log, None, "", None, "skipped", "skipped_outgoing")
                return
            if not event.is_private:
                await _handle_group_incoming(client, user_id, event, peer_id_for_log)
                return
            if not event.raw_text:
                await log_autoreply(user_id, peer_id_for_log, None, "", None, "skipped", "skipped_empty_text")
                return
            sender = await event.get_sender()
            if getattr(sender, "bot", False):
                await log_autoreply(user_id, peer_id_for_log, None, event.raw_text, None, "skipped", "skipped_bot_sender")
                return
            if _bot is None:
                logger.warning("Bot instance is not configured for user_id=%s", user_id)
                return
            peer_id = int(event.chat_id)
            peer_name = _sender_name(sender)
            
            # Create task with proper exception handling
            async def _process_message() -> None:
                try:
                    await enqueue_incoming_message(
                        _bot,
                        client,
                        IncomingPrivateMessage(user_id=user_id, peer_id=peer_id, peer_name=peer_name, text=event.raw_text, event_id=getattr(event, "id", None)),
                    )
                except Exception:
                    logger.exception("Failed to enqueue incoming message for user %s peer %s", user_id, peer_id)
            
            asyncio.create_task(_process_message())
        except FloodWaitError as exc:
            logger.warning("Incoming handler FloodWait user=%s seconds=%s", user_id, exc.seconds)
        except Exception:
            logger.exception("Incoming handler failed for user %s", user_id)

    @client.on(events.NewMessage(outgoing=True))
    async def on_outgoing(event):
        try:
            if not event.is_private or not event.chat_id:
                return
            async with async_session_maker() as session:
                await TelegramAccountRepository(session).mark_owner_outgoing(user_id, int(event.chat_id))
                await session.commit()
        except Exception:
            logger.exception("Outgoing activity tracking failed for user %s", user_id)


async def _handle_group_incoming(client: TelegramClient, user_id: int, event, chat_id: int) -> None:
    if not event.raw_text:
        return
    if _bot is None:
        return
    async with async_session_maker() as session:
        repo = LinkedGroupRepository(session)
        group = await repo.get(user_id, chat_id)
        if group is None or not group.is_active or not group.auto_reply_enabled:
            return
        user = await session.scalar(select(User).where(User.id == user_id))
        if user is None or not can_use_ai(user):
            await log_autoreply(user_id, chat_id, group.title, event.raw_text, None, "skipped", "skipped_limit")
            await session.commit()
            return
        title = group.title

    if not await _is_group_trigger_for_owner(client, event):
        return

    try:
        reply = await generate_ai_reply(user_id, chat_id, event.raw_text)
        await client.send_message(chat_id, reply, reply_to=getattr(event, "id", None))
    except FloodWaitError as exc:
        await log_autoreply(user_id, chat_id, title, event.raw_text, None, "failed", "failed_send", "groq", f"FloodWait: {exc.seconds}")
        return
    except Exception as exc:
        logger.exception("Group autoreply failed user_id=%s chat_id=%s", user_id, chat_id)
        await log_autoreply(user_id, chat_id, title, event.raw_text, None, "failed", "failed_group_reply", "groq", str(exc))
        return

    log_id = await log_autoreply(user_id, chat_id, title, event.raw_text, reply, "sent", provider="groq")
    async with async_session_maker() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if user:
            consume_ai_credit(user)
        settings = await TelegramAccountRepository(session).get_settings(user_id)
        await TelegramAccountRepository(session).consume_autoreply_credit(settings)
        await session.commit()
    try:
        await notify_owner_reply(_bot, user_id, f"{title} guruhi", event.raw_text, reply)
    except Exception:
        logger.exception("Could not notify owner about group reply log_id=%s", log_id)


async def _is_group_trigger_for_owner(client: TelegramClient, event) -> bool:
    me = await client.get_me()
    username = (getattr(me, "username", None) or "").lower()
    text = (event.raw_text or "").lower()
    if username and f"@{username}" in text:
        return True
    if not getattr(event, "is_reply", False):
        return False
    try:
        replied = await event.get_reply_message()
    except Exception:
        return False
    return bool(replied and int(getattr(replied, "sender_id", 0) or 0) == int(me.id))


def _start_schedule_worker(user_id: int, client: TelegramClient) -> None:
    task = _schedule_tasks.get(user_id)
    if task and not task.done():
        return
    _schedule_tasks[user_id] = asyncio.create_task(_schedule_loop(user_id, client))


async def _schedule_loop(user_id: int, client: TelegramClient) -> None:
    while True:
        try:
            await _send_due_group_schedules(user_id, client)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Group schedule loop failed for user %s", user_id)
        await asyncio.sleep(30)


async def _send_due_group_schedules(user_id: int, client: TelegramClient) -> None:
    now = datetime.utcnow()
    async with async_session_maker() as session:
        groups = await LinkedGroupRepository(session).due_schedules(user_id, now)
        for group in groups:
            text = (group.schedule_text or "").strip()
            if not text:
                group.schedule_enabled = False
                continue
            try:
                await client.send_message(group.chat_id, text)
                interval = max(1, int(group.schedule_interval_minutes or 60))
                group.schedule_next_run_at = now + timedelta(minutes=interval)
            except FloodWaitError as exc:
                group.schedule_next_run_at = now + timedelta(seconds=exc.seconds)
            except Exception as exc:
                logger.warning("Scheduled group message failed user=%s chat=%s error=%s", user_id, group.chat_id, exc)
                group.schedule_next_run_at = now + timedelta(minutes=5)
        await session.commit()


def _sender_name(sender) -> str | None:
    if sender is None:
        return None
    username = getattr(sender, "username", None)
    first_name = getattr(sender, "first_name", None)
    last_name = getattr(sender, "last_name", None)
    full = " ".join(part for part in [first_name, last_name] if part)
    return full or (f"@{username}" if username else None)


async def _disable_settings(user_id: int) -> None:
    async with async_session_maker() as session:
        await TelegramAccountRepository(session).set_autoreply_enabled(user_id, False)
        await session.commit()
