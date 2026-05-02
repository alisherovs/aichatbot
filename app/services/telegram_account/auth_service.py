from __future__ import annotations

from dataclasses import dataclass
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
)
from telethon.sessions import StringSession
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database.repositories import TelegramAccountRepository, UserRepository
from app.services.telegram_account.session_service import encrypt_session


class TelegramAuthError(Exception):
    pass


class TelegramTwoFactorRequired(TelegramAuthError):
    pass


@dataclass
class PendingLogin:
    client: TelegramClient
    phone: str
    phone_code_hash: str


_pending_logins: dict[int, PendingLogin] = {}


def _check_api_config() -> None:
    settings = get_settings()
    if not settings.telegram_api_id_int or not settings.telegram_api_hash:
        raise TelegramAuthError("TELEGRAM_API_ID yoki TELEGRAM_API_HASH sozlanmagan.")


def _new_client() -> TelegramClient:
    settings = get_settings()
    return TelegramClient(StringSession(), settings.telegram_api_id_int, settings.telegram_api_hash)


async def start_login(user_id: int, phone: str) -> None:
    _check_api_config()
    client = _new_client()
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
    except PhoneNumberInvalidError as exc:
        await client.disconnect()
        raise TelegramAuthError("Telefon raqam noto‘g‘ri. Masalan: +998901234567") from exc
    except FloodWaitError as exc:
        await client.disconnect()
        raise TelegramAuthError(f"Telegram limit qo‘ydi. {exc.seconds} soniyadan keyin urinib ko‘ring.") from exc
    _pending_logins[user_id] = PendingLogin(client=client, phone=phone, phone_code_hash=sent.phone_code_hash)


async def confirm_code(db_session: AsyncSession, user_id: int, code: str) -> None:
    pending = _pending_logins.get(user_id)
    if pending is None:
        raise TelegramAuthError("Login jarayoni topilmadi. Qaytadan boshlang.")
    try:
        await pending.client.sign_in(phone=pending.phone, code=code, phone_code_hash=pending.phone_code_hash)
    except SessionPasswordNeededError as exc:
        raise TelegramTwoFactorRequired("2FA parol kerak.") from exc
    except PhoneCodeInvalidError as exc:
        raise TelegramAuthError("Kod noto‘g‘ri. Qayta kiriting.") from exc
    except PhoneCodeExpiredError as exc:
        await pending.client.disconnect()
        _pending_logins.pop(user_id, None)
        raise TelegramAuthError("Kod muddati tugagan. Qaytadan boshlang.") from exc
    except FloodWaitError as exc:
        raise TelegramAuthError(f"Telegram limit qo‘ydi. {exc.seconds} soniyadan keyin urinib ko‘ring.") from exc
    await save_encrypted_session(db_session, user_id, pending.phone, pending.client.session.save())
    await pending.client.disconnect()
    _pending_logins.pop(user_id, None)


async def confirm_2fa_password(db_session: AsyncSession, user_id: int, password: str) -> None:
    pending = _pending_logins.get(user_id)
    if pending is None:
        raise TelegramAuthError("Login jarayoni topilmadi. Qaytadan boshlang.")
    try:
        await pending.client.sign_in(password=password)
    except PasswordHashInvalidError as exc:
        raise TelegramAuthError("2FA parol noto‘g‘ri.") from exc
    except FloodWaitError as exc:
        raise TelegramAuthError(f"Telegram limit qo‘ydi. {exc.seconds} soniyadan keyin urinib ko‘ring.") from exc
    await save_encrypted_session(db_session, user_id, pending.phone, pending.client.session.save())
    await pending.client.disconnect()
    _pending_logins.pop(user_id, None)


async def save_encrypted_session(db_session: AsyncSession, user_id: int, phone: str, session_string: str) -> None:
    encrypted = encrypt_session(session_string)
    repo = TelegramAccountRepository(db_session)
    await repo.save_session(user_id, phone, encrypted)
    settings = await repo.get_settings(user_id)
    settings.mode = "assistant_only"
    await UserRepository(db_session).link_account(user_id)


async def unlink_account(db_session: AsyncSession, user_id: int) -> None:
    await TelegramAccountRepository(db_session).delete_session(user_id)
    repo = TelegramAccountRepository(db_session)
    await repo.set_autoreply_enabled(user_id, False)
    await repo.set_autoreply_mode(user_id, "off")
    await UserRepository(db_session).unlink_account(user_id)
