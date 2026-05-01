from __future__ import annotations

import re
from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.config import get_settings


@dataclass(frozen=True)
class RequiredSubscription:
    title: str
    chat_id: str | int
    url: str | None


@dataclass(frozen=True)
class SubscriptionCheckResult:
    ok: bool
    missing: list[RequiredSubscription]


def get_required_subscriptions() -> list[RequiredSubscription]:
    items: list[RequiredSubscription] = []
    for raw in get_settings().required_subscription_items:
        item = _parse_required_subscription(raw)
        if item:
            items.append(item)
    return items


async def check_required_subscriptions(bot: Bot, user_id: int) -> SubscriptionCheckResult:
    missing: list[RequiredSubscription] = []
    for item in get_required_subscriptions():
        if not await _is_member(bot, item.chat_id, user_id):
            missing.append(item)
    return SubscriptionCheckResult(ok=not missing, missing=missing)


def required_subscription_text(missing: list[RequiredSubscription]) -> str:
    names = "\n".join(f"• <b>{item.title}</b>" for item in missing)
    return (
        "<b>🔒 Majburiy obuna</b>\n\n"
        "Botdan foydalanish uchun avval quyidagi kanal yoki guruhlarga a’zo bo‘ling:\n\n"
        f"{names}\n\n"
        "A’zo bo‘lganingizdan keyin <b>✅ Tekshirish</b> tugmasini bosing."
    )


def _parse_required_subscription(raw: str) -> RequiredSubscription | None:
    value = raw.strip()
    if not value:
        return None

    title: str | None = None
    if "|" in value:
        title_part, value = value.split("|", 1)
        title = title_part.strip() or None
        value = value.strip()

    url = _subscription_url(value)
    chat_id = _subscription_chat_id(value)
    if chat_id is None:
        return None

    if title is None:
        title = _subscription_title(value, chat_id)
    return RequiredSubscription(title=title, chat_id=chat_id, url=url)


def _subscription_chat_id(value: str) -> str | int | None:
    value = value.strip()
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith("@") and len(value) > 1:
        return value
    match = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]{5,})/?$", value)
    if match:
        return f"@{match.group(1)}"
    return None


def _subscription_url(value: str) -> str | None:
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("@") and len(value) > 1:
        return f"https://t.me/{value[1:]}"
    return None


def _subscription_title(value: str, chat_id: str | int) -> str:
    if isinstance(chat_id, str) and chat_id.startswith("@"):
        return chat_id
    return value


async def _is_member(bot: Bot, chat_id: str | int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    return member.status not in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, "left", "kicked"}
