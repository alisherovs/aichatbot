from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


TOOLS = {
    "write": "✍️ Matn yozish",
    "translate": "🌐 Tarjima qilish",
    "summarize": "📄 Qisqartirish",
    "rewrite": "🔁 Qayta yozish",
    "ideas": "💡 G‘oya berish",
    "hashtags": "🏷 Hashtag yaratish",
    "ad_copy": "📢 Reklama matni",
}


def tools_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, callback_data=f"tool:{key}")]
            for key, title in TOOLS.items()
        ]
        + [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")]]
    )


def tool_input_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="main:tools")]])
