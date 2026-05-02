from __future__ import annotations

from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


PLAN_LIMITS = {"free": 30, "pro": 150, "business": 300}
LIMIT_EXCEEDED_TEXT = (
    "Sizning bugungi AI limitingiz tugadi. Ertaga limit yana yangilanadi yoki Premium tarifga o‘tib, "
    "ko‘proq limitdan foydalanishingiz mumkin."
)


def get_plan_limit(plan: str) -> int:
    return PLAN_LIMITS.get((plan or "free").lower(), PLAN_LIMITS["free"])


def reset_daily_usage_if_needed(user) -> bool:
    today = date.today()
    if getattr(user, "limit_reset_date", None) != today:
        user.used_today = 0
        user.daily_limit = get_plan_limit(user.plan)
        user.limit_reset_date = today
        return True
    if user.daily_limit != get_plan_limit(user.plan):
        user.daily_limit = get_plan_limit(user.plan)
        return True
    return False


def can_use_ai(user) -> bool:
    reset_daily_usage_if_needed(user)
    return get_remaining_credits(user) > 0


def consume_ai_credit(user) -> None:
    reset_daily_usage_if_needed(user)
    daily_remaining = max(0, int(user.daily_limit or 0) - int(user.used_today or 0))
    if daily_remaining > 0:
        user.used_today = int(user.used_today or 0) + 1
        return
    if int(getattr(user, "bonus_credits", 0) or 0) > 0:
        user.bonus_credits = int(user.bonus_credits or 0) - 1


def get_remaining_credits(user) -> int:
    reset_daily_usage_if_needed(user)
    daily_remaining = max(0, int(user.daily_limit or 0) - int(user.used_today or 0))
    return daily_remaining + max(0, int(getattr(user, "bonus_credits", 0) or 0))


async def update_user_plan(session: AsyncSession, user_id: int, plan: str):
    from app.database.models import User

    plan = plan.lower()
    if plan not in PLAN_LIMITS:
        raise ValueError("Noma’lum tarif.")
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    user.plan = plan
    user.daily_limit = get_plan_limit(plan)
    user.used_today = 0
    user.limit_reset_date = date.today()
    await session.flush()
    return user


def limit_text(user) -> str:
    reset_daily_usage_if_needed(user)
    return f"{user.used_today}/{user.daily_limit} + bonus {getattr(user, 'bonus_credits', 0) or 0}"
