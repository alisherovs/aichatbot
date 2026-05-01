from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from app.database.models import User
from app.database.repositories import ReferralRepository, UserRepository
from app.keyboards.main_menu import main_menu
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, session: AsyncSession, command: CommandObject) -> None:
    referral_text = ""
    if command.args:
        ref_arg = command.args.strip()
        if ref_arg.startswith("ref_"):
            ref_arg = ref_arg.removeprefix("ref_")
        if ref_arg.isdigit():
            referrer = await UserRepository(session).get_by_telegram_id(int(ref_arg))
            if referrer and referrer.id != db_user.id:
                referral = await ReferralRepository(session).create_referral(referrer, db_user)
                if referral:
                    referral_text = "\n\n🎁 Sizga referal bonus sifatida 5 ta AI kredit berildi."
    text = (
        "<b>🤖 TeleMind AI</b>\n\n"
        "Telegram ichidagi aqlli shaxsiy yordamchingiz.\n\n"
        "Kerakli bo‘limni tanlang:"
        f"{referral_text}"
    )
    await message.answer(text, reply_markup=main_menu(db_user.role == "admin"))
