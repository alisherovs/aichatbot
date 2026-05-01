from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.repositories import UsageRepository
from app.keyboards.main_menu import back_main
from app.keyboards.tools import TOOLS, tool_input_keyboard, tools_keyboard
from app.services.ai.ai_service import AIServiceError, generate_tool_response
from app.services.usage_service import LIMIT_EXCEEDED_TEXT, can_use_ai, consume_ai_credit, get_remaining_credits
from app.states.tool_states import ToolStates
from app.utils.chat_action import run_with_typing

router = Router()


@router.callback_query(F.data == "main:tools")
async def tools_menu(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.clear()
    await callback.message.edit_text(
        "<b>🛠 AI vositalar</b>\n\nKerakli vositani tanlang.",
        reply_markup=tools_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tool:"))
async def select_tool(callback: CallbackQuery, state: FSMContext) -> None:
    tool_type = callback.data.split(":", 1)[1]
    title = TOOLS.get(tool_type)
    if not title:
        await callback.answer("Vosita topilmadi.", show_alert=True)
        return
    await state.set_state(ToolStates.waiting_for_input)
    await state.update_data(tool_type=tool_type, tool_title=title)
    await callback.message.edit_text(
        f"<b>{title}</b>\n\nMatn yoki so‘rovingizni yuboring.",
        reply_markup=tool_input_keyboard(),
    )
    await callback.answer()


@router.message(ToolStates.waiting_for_input, F.text)
async def handle_tool_input(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    if not can_use_ai(db_user):
        await message.answer(f"💎 <b>Limit tugadi</b>\n\n{LIMIT_EXCEEDED_TEXT}", reply_markup=back_main())
        return
    data = await state.get_data()
    tool_type = data.get("tool_type") or "write"
    waiting = await message.answer("⏳ Javob tayyorlanmoqda...")
    try:
        async def operation() -> str:
            return await generate_tool_response(db_user, tool_type, message.text)

        answer = await run_with_typing(message.bot, message.chat.id, operation)
    except AIServiceError as exc:
        await waiting.edit_text(f"⚠️ {exc}")
        return
    consume_ai_credit(db_user)
    await UsageRepository(session).log(db_user.id, f"tool:{tool_type}")
    await state.clear()
    await waiting.edit_text(answer, parse_mode=None)
