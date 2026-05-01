"""Persona selection keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.persona_service import list_personas


def persona_selection_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for persona selection."""
    buttons = []
    
    for persona in list_personas():
        button = InlineKeyboardButton(
            text=persona["title"],
            callback_data=f"persona:{persona['key']}"
        )
        buttons.append([button])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_menu_keyboard() -> InlineKeyboardMarkup:
    """Create back to menu button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")]
        ]
    )
