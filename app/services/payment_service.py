from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import PaymentRepository
from app.services.usage_service import get_plan_limit


@dataclass(frozen=True)
class StarsPlan:
    key: str
    title: str
    stars: int
    days: int


PLANS = {
    "pro": StarsPlan(key="pro", title="Pro", stars=100, days=30),
    "business": StarsPlan(key="business", title="Business", stars=250, days=30),
}


def get_stars_plan(plan: str) -> StarsPlan:
    key = plan.lower()
    if key not in PLANS:
        raise ValueError("Noma’lum tarif.")
    return PLANS[key]


def build_payload(user_id: int, plan: str) -> str:
    plan_data = get_stars_plan(plan)
    return f"stars:{plan_data.key}:{user_id}:{int(datetime.utcnow().timestamp())}"


async def create_pending_payment(session: AsyncSession, user, plan: str, payload: str):
    plan_data = get_stars_plan(plan)
    return await PaymentRepository(session).create_pending(
        user_id=user.id,
        telegram_id=user.telegram_id,
        plan=plan_data.key,
        amount_stars=plan_data.stars,
        payload=payload,
    )


async def activate_payment(session: AsyncSession, payment, telegram_payment_charge_id: str | None, provider_payment_charge_id: str | None):
    from app.database.models import User

    user = await session.get(User, payment.user_id)
    if user is None:
        raise ValueError("Foydalanuvchi topilmadi.")
    plan_data = get_stars_plan(payment.plan)
    payment.status = "paid"
    payment.telegram_payment_charge_id = telegram_payment_charge_id
    payment.provider_payment_charge_id = provider_payment_charge_id
    payment.paid_at = datetime.utcnow()
    user.plan = plan_data.key
    user.daily_limit = get_plan_limit(plan_data.key)
    user.used_today = 0
    user.premium_until = datetime.utcnow() + timedelta(days=plan_data.days)
    await session.flush()
    return user


def success_text(plan: str) -> str:
    if plan == "business":
        return (
            "✅ <b>Business tarif faollashtirildi!</b>\n\n"
            "Endi sizda:\n"
            "• Kuniga 300 ta AI javob\n"
            "• Kengaytirilgan imkoniyatlar\n"
            "• Ustuvor foydalanish\n\n"
            "Tarif muddati: 30 kun"
        )
    return (
        "✅ <b>Pro tarif faollashtirildi!</b>\n\n"
        "Endi sizda:\n"
        "• Kuniga 150 ta AI javob\n"
        "• AI vositalar\n"
        "• Ovozli AI imkoniyati\n\n"
        "Tarif muddati: 30 kun"
    )
