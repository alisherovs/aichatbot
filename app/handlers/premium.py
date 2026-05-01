from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, LabeledPrice
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.premium import premium_keyboard
from app.services.payment_service import build_payload, create_pending_payment, get_stars_plan
from app.services.usage_service import get_remaining_credits, reset_daily_usage_if_needed
from app.utils.formatting import fmt_dt

router = Router()


PLAN_BADGES = {"free": "Boshlang‘ich", "pro": "Faol premium", "business": "Maksimal imkoniyat"}


def premium_text(db_user: User) -> str:
    reset_daily_usage_if_needed(db_user)
    remaining = get_remaining_credits(db_user)
    plan = (db_user.plan or "free").lower()
    premium_until = fmt_dt(db_user.premium_until) if db_user.premium_until else "muddatsiz free"
    return (
        "💎 <b>TeleMind Premium</b>\n"
        "AI yordamchini ko‘proq, tezroq va qulayroq ishlatish uchun tarif tanlang.\n\n"
        "┌ <b>Sizning holatingiz</b>\n"
        f"├ Tarif: <b>{plan.title()}</b> · {PLAN_BADGES.get(plan, 'Faol')}\n"
        f"├ Bugungi limit: <b>{db_user.used_today}/{db_user.daily_limit}</b>\n"
        f"├ Qolgan javoblar: <b>{remaining}</b>\n"
        f"└ Muddati: <b>{premium_until}</b>\n\n"
        "⭐ <b>Pro</b> · <b>100 ⭐ / 30 kun</b>\n"
        "Kunlik 150 javob, AI chat, personajlar, prompt va yordamchi funksiyalaridan faol foydalanish uchun.\n\n"
        "🌟 <b>Business</b> · <b>250 ⭐ / 30 kun</b>\n"
        "Kunlik 300 javob, ko‘proq avtomatlashtirish, guruhlar va intensiv foydalanish uchun eng qulay tanlov.\n\n"
        "Pastdan tarifni ochib ko‘ring yoki darhol sotib oling."
    )


@router.callback_query(F.data == "main:premium")
async def premium_menu(callback: CallbackQuery, db_user: User) -> None:
    await callback.message.edit_text(premium_text(db_user), reply_markup=premium_keyboard())
    await callback.answer()


@router.callback_query(F.data.in_({"premium:details_pro", "premium:details_business"}))
async def premium_details(callback: CallbackQuery, db_user: User) -> None:
    plan_key = "pro" if callback.data == "premium:details_pro" else "business"
    plan = get_stars_plan(plan_key)
    if plan_key == "pro":
        text = (
            "⭐ <b>Pro tarif</b>\n\n"
            "<b>Kimlar uchun?</b>\n"
            "AI chatdan har kuni foydalanadigan, prompt/personajlar bilan ishlaydigan va limitga tez-tez yetib qoladigan userlar uchun.\n\n"
            "<b>Ichida nimalar bor?</b>\n"
            "• Kuniga <b>150 ta AI javob</b>\n"
            "• AI chat va personajlar\n"
            "• Doimiy prompt\n"
            "• Shaxsiy xabarlarga AI yordamchi\n"
            "• 30 kunlik premium muddat\n\n"
            f"<b>Narx:</b> {plan.stars} ⭐"
        )
    else:
        text = (
            "🌟 <b>Business tarif</b>\n\n"
            "<b>Kimlar uchun?</b>\n"
            "Botni ish, kanal/guruh, tezkor javoblar va ko‘proq avtomatlashtirish uchun ishlatadigan userlar uchun.\n\n"
            "<b>Ichida nimalar bor?</b>\n"
            "• Kuniga <b>300 ta AI javob</b>\n"
            "• AI yordamchi va guruh funksiyalari\n"
            "• Timer orqali guruhlarga xabar yuborish\n"
            "• Kengaytirilgan foydalanish limiti\n"
            "• 30 kunlik premium muddat\n\n"
            f"<b>Narx:</b> {plan.stars} ⭐"
        )
    await callback.message.edit_text(text, reply_markup=premium_keyboard())
    await callback.answer()


@router.callback_query(F.data.in_({"premium:buy_pro", "premium:buy_business"}))
async def premium_buy(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    plan_key = "pro" if callback.data == "premium:buy_pro" else "business"
    plan = get_stars_plan(plan_key)
    payload = build_payload(db_user.id, plan.key)
    await create_pending_payment(session, db_user, plan.key, payload)
    await session.commit()
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{plan.title} tarif",
        description=f"{plan.days} kunlik {plan.title} tarif",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{plan.title} tarif", amount=plan.stars)],
    )
    await callback.answer()


@router.callback_query(F.data == "premium:compare")
async def premium_compare(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📊 <b>Tariflarni solishtirish</b>\n\n"
        "<b>Free</b>\n"
        "• 30 javob / kun\n"
        "• Asosiy AI chat\n"
        "• Sinab ko‘rish uchun\n\n"
        "<b>⭐ Pro</b>\n"
        "• 150 javob / kun\n"
        "• Personajlar va doimiy prompt\n"
        "• Shaxsiy xabarlarga AI yordamchi\n"
        "• 100 ⭐ / 30 kun\n\n"
        "<b>🌟 Business</b>\n"
        "• 300 javob / kun\n"
        "• Guruh reply/metka javoblari\n"
        "• Timerli guruh xabarlari\n"
        "• 250 ⭐ / 30 kun",
        reply_markup=premium_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "premium:my_plan")
async def my_plan(callback: CallbackQuery, db_user: User) -> None:
    reset_daily_usage_if_needed(db_user)
    remaining = get_remaining_credits(db_user)
    used = int(db_user.used_today or 0)
    limit = max(1, int(db_user.daily_limit or 1))
    percent = min(100, round((used / limit) * 100))
    await callback.message.edit_text(
        "👤 <b>Mening tarifim</b>\n\n"
        f"Tarif: <b>{db_user.plan.title()}</b>\n"
        f"Holat: <b>{PLAN_BADGES.get((db_user.plan or 'free').lower(), 'Faol')}</b>\n"
        f"Kunlik limit: <b>{db_user.daily_limit}</b>\n"
        f"Bugun ishlatilgan: <b>{used}</b> ({percent}%)\n"
        f"Qolgan javoblar: <b>{remaining}</b>\n"
        f"Bonus kreditlar: <b>{db_user.bonus_credits}</b>\n"
        f"Premium muddati: <b>{fmt_dt(db_user.premium_until) if db_user.premium_until else '-'}</b>\n\n"
        "Limit har kuni yangilanadi. Premium sotib olinsa bugungi ishlatilgan limit ham yangidan boshlanadi.",
        reply_markup=premium_keyboard(),
    )
    await callback.answer()
