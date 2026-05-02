from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User
from app.database.repositories import UserRepository
from app.keyboards.prompt import prompt_keyboard
from app.states.prompt_states import PromptStates

router = Router()


@router.callback_query(F.data == "main:prompt")
async def prompt_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>🧠 Mening promptim</b>\n\n"
        "Doimiy prompt AI sizga qanday uslubda javob berishini belgilaydi.",
        reply_markup=prompt_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "prompt:view")
async def prompt_view(callback: CallbackQuery, db_user: User) -> None:
    text = db_user.custom_prompt or "Sizda hozircha doimiy prompt yo‘q."
    await callback.message.edit_text(f"<b>👁 Promptni ko‘rish</b>\n\n{text}", reply_markup=prompt_keyboard())
    await callback.answer()


@router.callback_query(F.data == "prompt:set")
async def prompt_set(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromptStates.waiting_for_prompt)
    await callback.message.edit_text(
        "<b>✏️ Doimiy prompt yozish</b>\n\n"
        "Doimiy prompt — bu AI sizga qanday uslubda javob berishini belgilaydigan sozlama.\n"
        "Masalan:\n"
        "• Menga qisqa va aniq javob ber.\n"
        "• Har doim misol bilan tushuntir.\n"
        "• Menga dasturlashni boshlovchidek tushuntir.\n\n"
        "Endi o‘zingizning doimiy promptingizni yuboring.",
        reply_markup=None,
    )
    await callback.answer()


@router.message(PromptStates.waiting_for_prompt, F.text)
async def save_prompt(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    await UserRepository(session).set_prompt(db_user.id, message.text.strip())
    await state.clear()
    await message.answer("✅ Doimiy prompt saqlandi. Endi AI javoblari shu uslubga moslashadi.", reply_markup=prompt_keyboard())


@router.callback_query(F.data == "prompt:clear")
async def prompt_reset(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    await UserRepository(session).set_prompt(db_user.id, None)
    await callback.message.edit_text("🧹 Doimiy prompt tozalandi.", reply_markup=prompt_keyboard())
    await callback.answer()


@router.callback_query(F.data == "prompt:info")
async def prompt_info(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>ℹ️ Prompt nima?</b>\n\n"
        "Prompt — AIga beriladigan yo‘l-yo‘riq. Doimiy prompt har bir javobga ta’sir qiladi, vaqtinchalik prompt esa faqat bitta so‘rov uchun ishlaydi.\n\n"
        "Masalan: “Menga qisqa, aniq va misol bilan javob ber.”",
        reply_markup=prompt_keyboard(),
    )
    await callback.answer()
