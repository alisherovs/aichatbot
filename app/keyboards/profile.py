from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💎 Premium", callback_data="main:premium"),
                InlineKeyboardButton(text="🧠 Prompt", callback_data="main:prompt"),
            ],
            [
                InlineKeyboardButton(text="💬 AI yordamchi", callback_data="autoreply:menu"),
                InlineKeyboardButton(text="👥 Guruhlar", callback_data="groups:menu"),
            ],
            [
                InlineKeyboardButton(text="🔗 Account ulash", callback_data="account:link"),
                InlineKeyboardButton(text="🔓 Uzish", callback_data="account:unlink"),
            ],
            [
                InlineKeyboardButton(text="🎁 Referal", callback_data="main:referral"),
                InlineKeyboardButton(text="🎟 Promokod", callback_data="promo:menu"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")],
        ]
    )


def profile_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="main:profile")]])
