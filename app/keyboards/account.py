from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def account_link_warning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Davom etish", callback_data="account:confirm_link")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="main:profile")],
        ]
    )


def auth_code_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1", callback_data="auth_digit:1"), InlineKeyboardButton(text="2", callback_data="auth_digit:2"), InlineKeyboardButton(text="3", callback_data="auth_digit:3")],
            [InlineKeyboardButton(text="4", callback_data="auth_digit:4"), InlineKeyboardButton(text="5", callback_data="auth_digit:5"), InlineKeyboardButton(text="6", callback_data="auth_digit:6")],
            [InlineKeyboardButton(text="7", callback_data="auth_digit:7"), InlineKeyboardButton(text="8", callback_data="auth_digit:8"), InlineKeyboardButton(text="9", callback_data="auth_digit:9")],
            [InlineKeyboardButton(text="⌫", callback_data="auth_delete"), InlineKeyboardButton(text="0", callback_data="auth_digit:0"), InlineKeyboardButton(text="✅", callback_data="auth_confirm")],
        ]
    )


def code_text(code: str) -> str:
    slots = list(code[:5]) + ["_"] * max(0, 5 - len(code))
    return "Telegramdan kelgan kodni pastdagi tugmalar orqali kiriting.\n\nKod: " + " ".join(slots[:5])
