from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def premium_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Pro", callback_data="premium:details_pro"),
                InlineKeyboardButton(text="🌟 Business", callback_data="premium:details_business"),
            ],
            [
                InlineKeyboardButton(text="⭐ Pro sotib olish", callback_data="premium:buy_pro"),
                InlineKeyboardButton(text="🌟 Business sotib olish", callback_data="premium:buy_business"),
            ],
            [InlineKeyboardButton(text="📊 Batafsil solishtirish", callback_data="premium:compare")],
            [InlineKeyboardButton(text="👤 Mening tarifim", callback_data="premium:my_plan")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")],
        ]
    )
