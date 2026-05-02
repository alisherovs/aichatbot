from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import PaymentRepository
from app.services.payment_service import activate_payment, success_text

router = Router()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession) -> None:
    payment = await PaymentRepository(session).get_by_payload(query.invoice_payload)
    if payment is None or payment.status != "pending":
        await query.answer(ok=False, error_message="To‘lov ma’lumoti topilmadi. Iltimos, qaytadan urinib ko‘ring.")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, session: AsyncSession) -> None:
    payment_info = message.successful_payment
    payment = await PaymentRepository(session).get_by_payload(payment_info.invoice_payload)
    if payment is None:
        await message.answer("To‘lov qabul qilindi, lekin tarifni faollashtirishda xatolik bo‘ldi. Iltimos, admin bilan bog‘laning.")
        return
    if payment.status == "paid":
        await message.answer("Bu to‘lov allaqachon faollashtirilgan.")
        return
    user = await activate_payment(
        session,
        payment,
        payment_info.telegram_payment_charge_id,
        payment_info.provider_payment_charge_id,
    )
    await message.answer(success_text(user.plan))
