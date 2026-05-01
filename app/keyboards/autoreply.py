from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def autoreply_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 AI yordamchini yoqish", callback_data="autoreply:on")],
            [InlineKeyboardButton(text="🔴 AI yordamchini o‘chirish", callback_data="autoreply:off")],
            [InlineKeyboardButton(text="👋 Faqat tanishtirish", callback_data="autoreply:assistant_only")],
            [InlineKeyboardButton(text="🤖 Avtomatik javob", callback_data="autoreply:auto")],
            [InlineKeyboardButton(text="✍️ Avval tasdiqlatish", callback_data="autoreply:confirm")],
            [InlineKeyboardButton(text="💤 Faqat men band bo‘lsam", callback_data="autoreply:away_only")],
            [InlineKeyboardButton(text="📊 Javoblar tarixi", callback_data="autoreply:history")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="main:profile")],
        ]
    )
