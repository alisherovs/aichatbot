import asyncio
import secrets
import string
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Payment, User
from app.database.repositories import AdminRepository, BonusRepository, PromoCodeRepository, UserRepository
from app.keyboards.admin import (
    admin_back_keyboard,
    admin_grant_users_keyboard,
    admin_keyboard,
    admin_plan_keyboard,
    broadcast_confirm_keyboard,
    promo_admin_keyboard,
    promo_credit_amount_keyboard,
    promo_max_uses_keyboard,
    promo_plan_days_keyboard,
    promo_plan_keyboard,
    promo_valid_days_keyboard,
)
from app.states.admin_states import AdminStates
from app.services.usage_service import get_plan_limit
from app.utils.admin import is_admin

router = Router()


def generate_promo_code(prefix: str) -> str:
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    return f"{prefix}{suffix}"


async def create_unique_promo_code(repo: PromoCodeRepository, prefix: str) -> str:
    normalized_prefix = "".join(ch for ch in prefix.upper() if ch.isalnum())[:12] or "PROMO"
    for _ in range(20):
        code = generate_promo_code(normalized_prefix)
        if await repo.get_by_code(code) is None:
            return code
    return generate_promo_code("PROMO")


def grant_user_text(target: User) -> str:
    name = " ".join(part for part in [target.first_name, target.last_name] if part) or target.username or "-"
    premium_until = target.premium_until.strftime("%Y-%m-%d") if target.premium_until else "-"
    return (
        "<b>👤 Foydalanuvchi tanlandi</b>\n\n"
        f"Ism: <b>{name}</b>\n"
        f"Telegram ID: <code>{target.telegram_id}</code>\n"
        f"Joriy tarif: <b>{target.plan.title()}</b>\n"
        f"Kunlik limit: <b>{target.daily_limit}</b>\n"
        f"Premium muddati: <b>{premium_until}</b>\n\n"
        "Qaysi tarif berilsin?"
    )


async def ensure_admin(callback: CallbackQuery, db_user: User) -> bool:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await callback.answer("Bu bo‘lim faqat adminlar uchun.", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "admin:panel")
async def admin_panel(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.clear()
    await callback.message.edit_text("<b>🛠 Admin paneli</b>\n\nKerakli bo‘limni tanlang:", reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    stats = await AdminRepository(session).stats()
    await callback.message.edit_text(
        f"<b>👤 Foydalanuvchilar</b>\n\nJami foydalanuvchilar: <b>{stats['total_users']}</b>\nFaol: <b>{stats['active_users']}</b>",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    stats = await AdminRepository(session).stats()
    await callback.message.edit_text(
        "<b>📊 Statistika</b>\n\n"
        f"Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"Faol foydalanuvchilar: <b>{stats['active_users']}</b>\n"
        f"Ulangan accountlar: <b>{stats['linked_accounts']}</b>\n"
        f"Premium foydalanuvchilar: <b>{stats['premium_users']}</b>\n"
        f"AI so‘rovlar: <b>{stats['ai_requests']}</b>\n"
        f"Muvaffaqiyatli to‘lovlar: <b>{stats['successful_payments']}</b>\n"
        f"Yig‘ilgan Stars: <b>{stats['stars_earned']}</b>\n"
        f"Promokodlar: <b>{stats['promo_codes']}</b>\n"
        f"Referallar: <b>{stats['referrals']}</b>\n"
        f"Berilgan bonuslar: <b>{stats['bonus_given']}</b>",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:grant_plan")
async def admin_grant_plan(callback: CallbackQuery, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.clear()
    rows = await session.execute(select(User).order_by(User.last_active_at.desc()).limit(10))
    users = list(rows.scalars().all())
    text = (
        "<b>💎 Tarif berish</b>\n\n"
        "Oxirgi faol foydalanuvchilardan birini tanlang yoki Telegram ID orqali qidiring."
    )
    await callback.message.edit_text(text, reply_markup=admin_grant_users_keyboard(users))
    await callback.answer()


@router.callback_query(F.data == "admin:grant_manual")
async def admin_grant_manual(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.set_state(AdminStates.waiting_for_grant_user)
    await callback.message.edit_text(
        "<b>🔎 ID orqali topish</b>\n\nTarif beriladigan foydalanuvchining Telegram ID raqamini yuboring.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:grant_user:"))
async def admin_grant_user_select(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    telegram_id_raw = callback.data.rsplit(":", 1)[1]
    if not telegram_id_raw.isdigit():
        await callback.answer("Noto‘g‘ri ID.", show_alert=True)
        return
    target = await UserRepository(session).get_by_telegram_id(int(telegram_id_raw))
    if target is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        grant_user_text(target),
        reply_markup=admin_plan_keyboard(target.telegram_id),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_grant_user, F.text)
async def admin_grant_user_input(message: Message, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await message.answer("Bu bo‘lim faqat adminlar uchun.")
        await state.clear()
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("Telegram ID faqat raqamlardan iborat bo‘lishi kerak.", reply_markup=admin_back_keyboard())
        return
    target = await UserRepository(session).get_by_telegram_id(int(raw))
    if target is None:
        await message.answer("Bunday foydalanuvchi topilmadi.", reply_markup=admin_back_keyboard())
        await state.clear()
        return
    await state.clear()
    await message.answer(
        grant_user_text(target),
        reply_markup=admin_plan_keyboard(target.telegram_id),
    )


@router.callback_query(F.data.startswith("admin:grant:"))
async def admin_grant_plan_finish(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    _, _, plan, telegram_id_raw = callback.data.split(":", 3)
    if plan not in {"free", "pro", "business"} or not telegram_id_raw.isdigit():
        await callback.answer("Noto‘g‘ri ma’lumot.", show_alert=True)
        return
    target = await UserRepository(session).get_by_telegram_id(int(telegram_id_raw))
    if target is None:
        await callback.message.edit_text("Foydalanuvchi topilmadi.", reply_markup=admin_back_keyboard())
        await callback.answer()
        return
    target.plan = plan
    target.daily_limit = get_plan_limit(plan)
    target.used_today = 0
    target.limit_reset_date = datetime.utcnow().date()
    target.premium_until = None if plan == "free" else datetime.utcnow() + timedelta(days=30)
    await AdminRepository(session).log_action(db_user.telegram_id, "grant_plan", target.telegram_id, f"plan={plan}")
    await callback.message.edit_text(
        f"<b>✅ Tarif berildi</b>\n\n"
        f"Telegram ID: <code>{target.telegram_id}</code>\n"
        f"Yangi tarif: <b>{plan.title()}</b>\n"
        f"Kunlik limit: <b>{target.daily_limit}</b>",
        reply_markup=admin_back_keyboard(),
    )
    try:
        await callback.bot.send_message(
            target.telegram_id,
            f"✅ Sizga <b>{plan.title()}</b> tarifi berildi.\nKunlik limitingiz: <b>{target.daily_limit}</b>",
        )
    except Exception:
        pass
    await callback.answer("Saqlandi")


@router.callback_query(F.data == "admin:bonus")
async def admin_bonus_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.set_state(AdminStates.waiting_for_bonus_user)
    await callback.message.edit_text(
        "<b>🎁 Bonus berish</b>\n\nBonus kredit beriladigan foydalanuvchining Telegram ID raqamini yuboring.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_bonus_user, F.text)
async def admin_bonus_user(message: Message, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await message.answer("Bu bo‘lim faqat adminlar uchun.")
        await state.clear()
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("Telegram ID faqat raqamlardan iborat bo‘lishi kerak.", reply_markup=admin_back_keyboard())
        return
    target = await UserRepository(session).get_by_telegram_id(int(raw))
    if target is None:
        await message.answer("Bunday foydalanuvchi topilmadi.", reply_markup=admin_back_keyboard())
        await state.clear()
        return
    await state.update_data(target_telegram_id=target.telegram_id)
    await state.set_state(AdminStates.waiting_for_bonus_amount)
    await message.answer(
        f"<b>🎁 Bonus miqdori</b>\n\nFoydalanuvchi: <code>{target.telegram_id}</code>\nHozirgi bonus: <b>{target.bonus_credits}</b>\n\nBeriladigan bonus kredit sonini yuboring.",
        reply_markup=admin_back_keyboard(),
    )


@router.message(AdminStates.waiting_for_bonus_amount, F.text)
async def admin_bonus_amount(message: Message, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await message.answer("Bu bo‘lim faqat adminlar uchun.")
        await state.clear()
        return
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("Bonus miqdori musbat raqam bo‘lishi kerak.", reply_markup=admin_back_keyboard())
        return
    data = await state.get_data()
    target = await UserRepository(session).get_by_telegram_id(int(data["target_telegram_id"]))
    if target is None:
        await message.answer("Foydalanuvchi topilmadi.", reply_markup=admin_back_keyboard())
        await state.clear()
        return
    amount = int(raw)
    await BonusRepository(session).add_bonus(target, amount, "admin", admin_id=db_user.telegram_id, reason="Admin tomonidan berildi")
    await AdminRepository(session).log_action(db_user.telegram_id, "bonus_grant", target.telegram_id, f"amount={amount}")
    await state.clear()
    await message.answer(
        f"<b>✅ Bonus berildi</b>\n\nTelegram ID: <code>{target.telegram_id}</code>\nBonus: <b>{amount}</b>\nJami bonus: <b>{target.bonus_credits}</b>",
        reply_markup=admin_back_keyboard(),
    )
    try:
        await message.bot.send_message(target.telegram_id, f"🎁 Sizga <b>{amount}</b> ta bonus AI kredit berildi.")
    except Exception:
        pass


@router.callback_query(F.data == "admin:payments")
async def admin_payments(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    stats = await AdminRepository(session).stats()
    rows = await session.execute(select(Payment).order_by(Payment.created_at.desc()).limit(10))
    payments = rows.scalars().all()
    parts = [
        "<b>💰 To‘lovlar</b>",
        f"\nMuvaffaqiyatli to‘lovlar: <b>{stats['successful_payments']}</b>",
        f"Yig‘ilgan Stars: <b>{stats['stars_earned']}</b>",
    ]
    if payments:
        parts.append("\nOxirgi 10 to‘lov:")
        for payment in payments:
            parts.append(
                f"• {payment.plan} | {payment.amount_stars} ⭐ | {payment.status} | <code>{payment.telegram_id or '-'}</code>"
            )
    else:
        parts.append("\nHozircha to‘lovlar yo‘q.")
    await callback.message.edit_text("\n".join(parts), reply_markup=admin_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:promos")
async def admin_promos(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    promos = await PromoCodeRepository(session).latest(10)
    parts = ["<b>🎟 Promokodlar</b>"]
    if promos:
        parts.append("\nOxirgi promokodlar:")
        for promo in promos:
            reward = f"{promo.credits} kredit" if promo.reward_type == "credits" else f"{promo.plan} / {promo.plan_days} kun"
            active = "faol" if promo.is_active else "o‘chiq"
            parts.append(f"• <code>{promo.code}</code> — {reward} — {promo.used_count}/{promo.max_uses} — {active}")
    else:
        parts.append("\nHozircha promokodlar yo‘q.")
    parts.append("\nYangi promokodni pastdagi tugmalar orqali yarating.")
    await callback.message.edit_text("\n".join(parts), reply_markup=promo_admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:promo_create_credits")
async def admin_promo_create_credits(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.clear()
    await callback.message.edit_text(
        "<b>🎁 Kredit promokod yaratish</b>\n\n"
        "Promokod nechta bonus kredit bersin?",
        reply_markup=promo_credit_amount_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_credit_amount:"))
async def admin_promo_credit_amount(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    amount = int(callback.data.rsplit(":", 1)[1])
    await state.update_data(promo_credits=amount)
    await callback.message.edit_text(
        f"<b>🎁 Kredit promokod</b>\n\nMukofot: <b>{amount}</b> kredit\n\nNecha marta ishlatilsin?",
        reply_markup=promo_max_uses_keyboard("credits"),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_promo_credits, F.text)
async def admin_promo_credits_finish(message: Message, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await message.answer("Bu bo‘lim faqat adminlar uchun.")
        await state.clear()
        return
    parts = message.text.strip().split()
    if len(parts) != 4 or not parts[1].isdigit() or not parts[2].isdigit() or not parts[3].isdigit():
        await message.answer("Format noto‘g‘ri. Masalan: <code>WELCOME50 50 100 30</code>", reply_markup=admin_back_keyboard())
        return
    code = parts[0].upper()
    credits, max_uses, valid_days = map(int, parts[1:])
    if credits <= 0 or max_uses <= 0:
        await message.answer("Kredit va limit musbat bo‘lishi kerak.", reply_markup=admin_back_keyboard())
        return
    repo = PromoCodeRepository(session)
    if await repo.get_by_code(code):
        await message.answer("Bu promokod allaqachon mavjud.", reply_markup=admin_back_keyboard())
        return
    expires_at = datetime.utcnow() + timedelta(days=valid_days) if valid_days else None
    promo = await repo.create(code, "credits", db_user.telegram_id, credits=credits, max_uses=max_uses, expires_at=expires_at)
    await AdminRepository(session).log_action(db_user.telegram_id, "promo_create", details=f"code={promo.code}, credits={credits}")
    await state.clear()
    await message.answer(
        f"<b>✅ Promokod yaratildi</b>\n\nKod: <code>{promo.code}</code>\nMukofot: <b>{credits}</b> kredit\nLimit: <b>{max_uses}</b>",
        reply_markup=promo_admin_keyboard(),
    )


@router.callback_query(F.data == "admin:promo_create_plan")
async def admin_promo_create_plan(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.clear()
    await callback.message.edit_text(
        "<b>💎 Tarif promokod yaratish</b>\n\n"
        "Promokod qaysi tarifni faollashtirsin?",
        reply_markup=promo_plan_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_plan_type:"))
async def admin_promo_plan_type(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    plan = callback.data.rsplit(":", 1)[1]
    if plan not in {"pro", "business"}:
        await callback.answer("Noto‘g‘ri tarif.", show_alert=True)
        return
    await state.update_data(promo_plan=plan)
    await callback.message.edit_text(
        f"<b>💎 Tarif promokod</b>\n\nTarif: <b>{plan.title()}</b>\n\nTarif muddati qancha bo‘lsin?",
        reply_markup=promo_plan_days_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_plan_days:"))
async def admin_promo_plan_days(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    days = int(callback.data.rsplit(":", 1)[1])
    await state.update_data(promo_plan_days=days)
    data = await state.get_data()
    plan = data.get("promo_plan", "pro")
    await callback.message.edit_text(
        f"<b>💎 Tarif promokod</b>\n\nTarif: <b>{str(plan).title()}</b>\nMuddat: <b>{days} kun</b>\n\nNecha marta ishlatilsin?",
        reply_markup=promo_max_uses_keyboard("plan"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_uses:"))
async def admin_promo_uses(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    _, _, kind, uses_raw = callback.data.split(":", 3)
    if kind not in {"credits", "plan"} or not uses_raw.isdigit():
        await callback.answer("Noto‘g‘ri ma’lumot.", show_alert=True)
        return
    await state.update_data(promo_kind=kind, promo_max_uses=int(uses_raw))
    title = "Kredit promokod" if kind == "credits" else "Tarif promokod"
    await callback.message.edit_text(
        f"<b>{title}</b>\n\nIshlatish limiti: <b>{uses_raw}</b>\n\nPromokod amal qilish muddati qancha bo‘lsin?",
        reply_markup=promo_valid_days_keyboard(kind),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_valid:"))
async def admin_promo_valid(callback: CallbackQuery, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    _, _, kind, valid_raw = callback.data.split(":", 3)
    if kind not in {"credits", "plan"} or not valid_raw.isdigit():
        await callback.answer("Noto‘g‘ri ma’lumot.", show_alert=True)
        return
    data = await state.get_data()
    max_uses = int(data.get("promo_max_uses") or 0)
    valid_days = int(valid_raw)
    if max_uses <= 0:
        await callback.answer("Limit topilmadi. Qaytadan yarating.", show_alert=True)
        return

    repo = PromoCodeRepository(session)
    expires_at = datetime.utcnow() + timedelta(days=valid_days) if valid_days else None
    if kind == "credits":
        credits = int(data.get("promo_credits") or 0)
        if credits <= 0:
            await callback.answer("Kredit miqdori topilmadi. Qaytadan yarating.", show_alert=True)
            return
        code = await create_unique_promo_code(repo, f"BONUS{credits}")
        promo = await repo.create(code, "credits", db_user.telegram_id, credits=credits, max_uses=max_uses, expires_at=expires_at)
        details = f"code={promo.code}, credits={credits}"
        result_text = (
            "<b>✅ Kredit promokod yaratildi</b>\n\n"
            f"Kod: <code>{promo.code}</code>\n"
            f"Mukofot: <b>{credits}</b> kredit\n"
            f"Limit: <b>{max_uses}</b>\n"
            f"Amal qilish: <b>{valid_days or 'muddatsiz'}</b>"
        )
    else:
        plan = str(data.get("promo_plan") or "")
        plan_days = int(data.get("promo_plan_days") or 0)
        if plan not in {"pro", "business"} or plan_days <= 0:
            await callback.answer("Tarif ma’lumoti topilmadi. Qaytadan yarating.", show_alert=True)
            return
        code = await create_unique_promo_code(repo, f"{plan.upper()}{plan_days}")
        promo = await repo.create(
            code,
            "plan",
            db_user.telegram_id,
            plan=plan,
            plan_days=plan_days,
            max_uses=max_uses,
            expires_at=expires_at,
        )
        details = f"code={promo.code}, plan={plan}, days={plan_days}"
        result_text = (
            "<b>✅ Tarif promokod yaratildi</b>\n\n"
            f"Kod: <code>{promo.code}</code>\n"
            f"Tarif: <b>{plan.title()}</b>\n"
            f"Muddat: <b>{plan_days} kun</b>\n"
            f"Limit: <b>{max_uses}</b>\n"
            f"Amal qilish: <b>{valid_days or 'muddatsiz'}</b>"
        )
    await AdminRepository(session).log_action(db_user.telegram_id, "promo_create", details=details)
    await state.clear()
    await callback.message.edit_text(result_text, reply_markup=promo_admin_keyboard())
    await callback.answer("Promokod yaratildi")


@router.message(AdminStates.waiting_for_promo_plan, F.text)
async def admin_promo_plan_finish(message: Message, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await message.answer("Bu bo‘lim faqat adminlar uchun.")
        await state.clear()
        return
    parts = message.text.strip().split()
    if len(parts) != 5 or parts[1].lower() not in {"pro", "business"} or not parts[2].isdigit() or not parts[3].isdigit() or not parts[4].isdigit():
        await message.answer("Format noto‘g‘ri. Masalan: <code>PRO30 pro 30 50 30</code>", reply_markup=admin_back_keyboard())
        return
    code = parts[0].upper()
    plan = parts[1].lower()
    plan_days = int(parts[2])
    max_uses = int(parts[3])
    valid_days = int(parts[4])
    if plan_days <= 0 or max_uses <= 0:
        await message.answer("Tarif kuni va limit musbat bo‘lishi kerak.", reply_markup=admin_back_keyboard())
        return
    repo = PromoCodeRepository(session)
    if await repo.get_by_code(code):
        await message.answer("Bu promokod allaqachon mavjud.", reply_markup=admin_back_keyboard())
        return
    expires_at = datetime.utcnow() + timedelta(days=valid_days) if valid_days else None
    promo = await repo.create(code, "plan", db_user.telegram_id, plan=plan, plan_days=plan_days, max_uses=max_uses, expires_at=expires_at)
    await AdminRepository(session).log_action(db_user.telegram_id, "promo_create", details=f"code={promo.code}, plan={plan}")
    await state.clear()
    await message.answer(
        f"<b>✅ Tarif promokod yaratildi</b>\n\nKod: <code>{promo.code}</code>\nTarif: <b>{plan.title()}</b>\nMuddat: <b>{plan_days} kun</b>\nLimit: <b>{max_uses}</b>",
        reply_markup=promo_admin_keyboard(),
    )


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text(
        "<b>📢 Xabar yuborish</b>\n\nFoydalanuvchilarga yuboriladigan xabar matnini kiriting. Keyingi oynada tasdiqlaysiz.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast, F.text)
async def admin_broadcast_input(message: Message, db_user: User, state: FSMContext) -> None:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await message.answer("Bu bo‘lim faqat adminlar uchun.")
        await state.clear()
        return
    await state.update_data(broadcast_text=message.text)
    await message.answer(
        "<b>📢 Tasdiqlash</b>\n\nXabar barcha bloklanmagan foydalanuvchilarga yuboriladi. Tasdiqlaysizmi?",
        reply_markup=broadcast_confirm_keyboard(),
    )


@router.callback_query(F.data == "admin:broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_admin(callback, db_user):
        return
    data = await state.get_data()
    text = data.get("broadcast_text")
    rows = await session.execute(select(User.telegram_id).where(User.is_banned.is_(False)))
    user_ids = list(rows.scalars().all())
    sent = 0
    failed = 0
    for telegram_id in user_ids:
        try:
            await callback.bot.send_message(telegram_id, text)
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1
    await AdminRepository(session).log_action(db_user.telegram_id, "broadcast", details=f"sent={sent}, failed={failed}")
    await state.clear()
    await callback.message.edit_text(
        f"<b>✅ Xabar yuborildi</b>\n\nYuborildi: <b>{sent}</b>\nYuborilmadi: <b>{failed}</b>",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:ban")
async def admin_ban(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await state.set_state(AdminStates.waiting_for_ban_user)
    await callback.message.edit_text(
        "<b>🚫 Bloklash</b>\n\nBloklanadigan foydalanuvchining Telegram ID raqamini yuboring.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_ban_user, F.text)
async def admin_ban_input(message: Message, db_user: User, state: FSMContext, session: AsyncSession) -> None:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await message.answer("Bu bo‘lim faqat adminlar uchun.")
        await state.clear()
        return
    target = message.text.strip()
    if not target.isdigit():
        await message.answer("Telegram ID faqat raqamlardan iborat bo‘lishi kerak.", reply_markup=admin_back_keyboard())
        return
    user = await UserRepository(session).get_by_telegram_id(int(target))
    if user is None:
        await message.answer("Bunday foydalanuvchi topilmadi.", reply_markup=admin_back_keyboard())
        await state.clear()
        return
    user.is_banned = True
    await AdminRepository(session).log_action(db_user.telegram_id, "ban_user", target_user_id=user.telegram_id)
    await state.clear()
    await message.answer(
        f"<b>🚫 Foydalanuvchi bloklandi</b>\n\nTelegram ID: <code>{user.telegram_id}</code>",
        reply_markup=admin_back_keyboard(),
    )


@router.callback_query(F.data == "admin:logs")
async def admin_logs(callback: CallbackQuery, db_user: User) -> None:
    if not await ensure_admin(callback, db_user):
        return
    await callback.message.edit_text(
        "<b>🧾 Loglar</b>\n\nServer loglari terminal/log collector orqali yuritiladi. Bot ichida xavfsiz qisqa ko‘rinish uchun modul joyi tayyor.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()
