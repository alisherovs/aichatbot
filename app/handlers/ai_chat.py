import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.repositories import ConversationRepository, UsageRepository
from app.keyboards.main_menu import back_main
from app.services.ai.ai_service import AIServiceError, generate_chat_response
from app.services.usage_service import LIMIT_EXCEEDED_TEXT, can_use_ai, consume_ai_credit, get_remaining_credits, limit_text, reset_daily_usage_if_needed
from app.states.chat_states import AIChatStates
from app.utils.chat_action import run_with_typing

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "main:ai_chat")
async def ai_chat_menu(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    reset_daily_usage_if_needed(db_user)
    await state.set_state(AIChatStates.chatting)
    await callback.message.edit_text(
        "<b>🤖 AI bilan suhbat</b>\n\n"
        "Oddiy savol bersangiz qisqa va aniq javob olasiz. Kattaroq savollarda esa AI batafsilroq, tartibli va ravon tushuntiradi.\n\n"
        "Savolingizni yozing.\n\n"
        f"Bugungi limit: <b>{limit_text(db_user)}</b>\nQolgan limit: <b>{get_remaining_credits(db_user)}</b>",
        reply_markup=back_main(),
    )
    await callback.answer()


@router.message(AIChatStates.chatting, F.text)
async def handle_ai_chat(message: Message, db_user: User, session: AsyncSession) -> None:
    if not can_use_ai(db_user):
        await message.answer(f"💎 <b>Limit tugadi</b>\n\n{LIMIT_EXCEEDED_TEXT}", reply_markup=back_main())
        return
    waiting = await message.answer("⏳ Javob tayyorlanmoqda...")
    conv_repo = ConversationRepository(session)
    conversation = await conv_repo.get_or_create_active(db_user.id)
    recent = await conv_repo.recent_messages(conversation.id, limit=8)
    context = [{"role": item.role, "content": item.content} for item in recent if item.role in {"user", "assistant"}]
    await conv_repo.add_message(db_user.id, conversation.id, "user", message.text)
    try:
        async def operation() -> str:
            return await generate_chat_response(db_user, message.text, context=context)

        answer = await run_with_typing(message.bot, message.chat.id, operation)
    except AIServiceError as exc:
        await waiting.edit_text(f"⚠️ {exc}")
        return
    await conv_repo.add_message(db_user.id, conversation.id, "assistant", answer)
    consume_ai_credit(db_user)
    await UsageRepository(session).log(db_user.id, "ai_chat")
    logger.debug("AI generated user_id=%s mode=chat", db_user.id)
    await waiting.edit_text(answer, parse_mode=None)
