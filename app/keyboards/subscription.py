from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.subscription_service import RequiredSubscription


def required_subscription_keyboard(missing: list[RequiredSubscription]) -> InlineKeyboardMarkup:
    rows = []
    for item in missing:
        if item.url:
            rows.append([InlineKeyboardButton(text=f"➕ {item.title}", url=item.url)])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="force_sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
