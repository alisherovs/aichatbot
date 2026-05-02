from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def legal_consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Shartlar", callback_data="legal:terms"),
                InlineKeyboardButton(text="🔐 Maxfiylik", callback_data="legal:privacy"),
            ],
            [InlineKeyboardButton(text="✅ Roziman", callback_data="legal:accept")],
        ]
    )


def legal_document_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Roziman", callback_data="legal:accept")],
            [InlineKeyboardButton(text="⬅️ Rozilik oynasi", callback_data="legal:consent")],
        ]
    )
