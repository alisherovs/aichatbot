from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👁 Promptni ko‘rish", callback_data="prompt:view")],
            [InlineKeyboardButton(text="✏️ Doimiy prompt yozish", callback_data="prompt:set")],
            [InlineKeyboardButton(text="🧹 Promptni tozalash", callback_data="prompt:clear")],
            [InlineKeyboardButton(text="ℹ️ Prompt nima?", callback_data="prompt:info")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")],
        ]
    )
