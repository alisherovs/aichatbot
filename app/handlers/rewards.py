from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.repositories import PromoCodeRepository, ReferralRepository
from app.keyboards.main_menu import back_main
from app.states.reward_states import RewardStates
from app.utils.security import safe_html

router = Router()


def promo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎟 Promokod kiritish", callback_data="promo:redeem")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")],
        ]
    )


@router.callback_query(F.data == "main:referral")
async def referral_menu(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    me = await callback.bot.get_me()
    stats = await ReferralRepository(session).stats_for_user(db_user.id)
    link = f"https://t.me/{me.username}?start=ref_{db_user.telegram_id}"
    await callback.message.edit_text(
        "<b>🎁 Referal tizimi</b>\n\n"
        "Do‘stingiz sizning havolangiz orqali botga kirsa:\n"
        f"• Sizga <b>{stats['referrer_bonus']}</b> ta bonus AI kredit\n"
        f"• Do‘stingizga <b>{stats['referred_bonus']}</b> ta bonus AI kredit beriladi\n\n"
        f"Taklif qilinganlar: <b>{stats['total']}</b>\n"
        f"Sizning bonus kreditlaringiz: <b>{db_user.bonus_credits}</b>\n\n"
        f"Referal havola:\n<code>{safe_html(link)}</code>",
        reply_markup=back_main(),
    )
    await callback.answer()


@router.callback_query(F.data == "promo:menu")
async def promo_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>🎟 Promokod</b>\n\nPromokodingiz bo‘lsa, uni kiritib bonus kredit yoki tarif faollashtirishingiz mumkin.",
        reply_markup=promo_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "promo:redeem")
async def promo_redeem_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RewardStates.waiting_for_promo_code)
    await callback.message.edit_text(
        "<b>🎟 Promokod kiritish</b>\n\nPromokodni yuboring. Masalan: <code>PRO30</code>",
        reply_markup=back_main(),
    )
    await callback.answer()


@router.message(RewardStates.waiting_for_promo_code, F.text)
async def promo_redeem_finish(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    code = message.text.strip().upper()
    repo = PromoCodeRepository(session)
    promo = await repo.get_by_code(code)
    if promo is None:
        await message.answer("Bunday promokod topilmadi.", reply_markup=promo_keyboard())
        return
    if not promo.is_active:
        await message.answer("Bu promokod faol emas.", reply_markup=promo_keyboard())
        return
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        await message.answer("Bu promokod muddati tugagan.", reply_markup=promo_keyboard())
        return
    if promo.used_count >= promo.max_uses:
        await message.answer("Bu promokod ishlatish limiti tugagan.", reply_markup=promo_keyboard())
        return
    if await repo.user_redeemed(db_user.id, promo.id):
        await message.answer("Siz bu promokoddan allaqachon foydalangansiz.", reply_markup=promo_keyboard())
        return

    await repo.redeem(db_user, promo)
    await state.clear()
    if promo.reward_type == "credits":
        text = f"✅ Promokod qabul qilindi. Sizga <b>{promo.credits}</b> ta bonus AI kredit qo‘shildi."
    else:
        text = f"✅ Promokod qabul qilindi. <b>{safe_html((promo.plan or '').title())}</b> tarifi faollashtirildi."
    await message.answer(text, reply_markup=back_main())
