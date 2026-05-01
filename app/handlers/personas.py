"""Persona selection handler."""

from __future__ import annotations

import logging

from aiogram import F, Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.repositories import UserRepository
from app.keyboards.personas import persona_selection_keyboard
from app.services.persona_service import get_persona_short_title, get_persona_title, list_personas

logger = logging.getLogger(__name__)

router = Router(name="personas")


@router.callback_query(F.data == "show_personas")
async def show_personas_menu(query: types.CallbackQuery, session: AsyncSession, db_user: User) -> None:
    """Show personas selection menu."""
    await query.answer()
    
    text = (
        "🎭 <b>AI Personajlar</b>\n\n"
        "Quyidagi personajlardan birini tanlang. "
        "Siz tanlagan personaj normal AI chat va private xabar javob beruvchi AI-da ishlatiladi.\n"
    )
    
    for persona in list_personas():
        text += f"\n{persona['title']}\n{persona['description']}\n"
    
    await query.message.edit_text(
        text,
        reply_markup=persona_selection_keyboard(),
    )


@router.callback_query(F.data.startswith("persona:"))
async def select_persona(query: types.CallbackQuery, session: AsyncSession, db_user: User) -> None:
    """Handle persona selection."""
    persona_key = query.data.split(":", 1)[1]
    
    # Validate persona exists
    if not any(p["key"] == persona_key for p in list_personas()):
        await query.answer("❌ Personaj topilmadi.", show_alert=True)
        return
    
    # Update user's selected persona
    db_user.selected_persona = persona_key
    await session.commit()
    
    persona_title = get_persona_title(persona_key)
    
    await query.answer(f"✅ {persona_title} tanlandi!", show_alert=True)
    
    # Show confirmation message
    await query.message.edit_text(
        f"✅ <b>Personaj yangilandi:</b> {persona_title}\n\n"
        "Endi oddiy AI chat va shaxsiy xabarlarga javob beruvchi AI shu uslubda javob beradi.",
        reply_markup=persona_selection_keyboard(),
    )
    
    logger.info("User %s selected persona: %s", db_user.id, persona_key)
