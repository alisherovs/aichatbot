from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database.models import TelegramSession
from app.database.repositories import TelegramAccountRepository


class SessionSecurityError(Exception):
    pass


def ensure_encryption_key() -> bytes:
    key = get_settings().session_encryption_key
    if not key:
        raise SessionSecurityError("SESSION_ENCRYPTION_KEY sozlanmagan.")
    try:
        Fernet(key.encode())
    except Exception as exc:
        raise SessionSecurityError("SESSION_ENCRYPTION_KEY noto‘g‘ri. Fernet.generate_key() bilan yarating.") from exc
    return key.encode()


def generate_encryption_key() -> str:
    return Fernet.generate_key().decode()


def encrypt_session(session_string: str) -> str:
    return Fernet(ensure_encryption_key()).encrypt(session_string.encode()).decode()


def decrypt_session(encrypted_session: str) -> str:
    try:
        return Fernet(ensure_encryption_key()).decrypt(encrypted_session.encode()).decode()
    except InvalidToken as exc:
        raise SessionSecurityError("Telegram session shifrini ochib bo‘lmadi.") from exc


async def get_user_session(session: AsyncSession, user_id: int) -> TelegramSession | None:
    return await TelegramAccountRepository(session).get_session(user_id)


async def delete_user_session(session: AsyncSession, user_id: int) -> None:
    await TelegramAccountRepository(session).delete_session(user_id)
