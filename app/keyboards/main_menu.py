from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🤖 AI bilan suhbat", callback_data="main:ai_chat"))
    kb.row(InlineKeyboardButton(text="🎭 Personajlar", callback_data="show_personas"))
    kb.row(
        InlineKeyboardButton(text="🧠 Mening promptim", callback_data="main:prompt"),
        InlineKeyboardButton(text="🛠 AI vositalar", callback_data="main:tools"),
    )
    kb.row(
        InlineKeyboardButton(text="👤 Profilim", callback_data="main:profile"),
        InlineKeyboardButton(text="🔗 Account ulash", callback_data="account:link"),
    )
    kb.row(
        InlineKeyboardButton(text="💬 AI yordamchi", callback_data="autoreply:menu"),
        InlineKeyboardButton(text="💎 Premium", callback_data="main:premium"),
    )
    kb.row(
        InlineKeyboardButton(text="🎁 Referal", callback_data="main:referral"),
        InlineKeyboardButton(text="🎟 Promokod", callback_data="promo:menu"),
    )
    kb.row(
        InlineKeyboardButton(text="❓ Yordam", callback_data="main:help"),
    )
    kb.row(
        InlineKeyboardButton(text="📄 Shartlar", callback_data="main:terms"),
        InlineKeyboardButton(text="🔐 Maxfiylik", callback_data="main:privacy"),
    )
    if is_admin:
        kb.row(InlineKeyboardButton(text="🛠 Admin paneli", callback_data="admin:panel"))
    return kb.as_markup()


def back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")]])


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 AI bilan suhbat", callback_data="main:ai_chat")],
            [
                InlineKeyboardButton(text="📄 Shartlar", callback_data="main:terms"),
                InlineKeyboardButton(text="🔐 Maxfiylik", callback_data="main:privacy"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")],
        ]
    )
