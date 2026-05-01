from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def groups_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Guruh tanlash", callback_data="groups:list:0")],
            [InlineKeyboardButton(text="📋 Bog‘langan guruhlar", callback_data="groups:selected")],
            [InlineKeyboardButton(text="⏱ Timer sozlash", callback_data="groups:schedule")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="main:profile")],
        ]
    )


def group_list_keyboard(groups: list[dict], selected_ids: set[int], page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    start = page * per_page
    items = groups[start : start + per_page]
    rows = []
    for group in items:
        chat_id = int(group["id"])
        mark = "✅" if chat_id in selected_ids else "☑️"
        title = (group.get("title") or str(chat_id))[:40]
        rows.append([InlineKeyboardButton(text=f"{mark} {title}", callback_data=f"groups:toggle:{chat_id}:{page}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"groups:list:{page - 1}"))
    if start + per_page < len(groups):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"groups:list:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="groups:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def selected_groups_keyboard(groups: list) -> InlineKeyboardMarkup:
    rows = []
    for group in groups[:20]:
        rows.append([InlineKeyboardButton(text=f"🗑 {(group.title or str(group.chat_id))[:40]}", callback_data=f"groups:remove:{group.chat_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="groups:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_groups_keyboard(groups: list) -> InlineKeyboardMarkup:
    rows = []
    for group in groups[:20]:
        status = "🟢" if group.schedule_enabled else "⚪️"
        rows.append([InlineKeyboardButton(text=f"{status} {(group.title or str(group.chat_id))[:40]}", callback_data=f"groups:schedule_group:{group.chat_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="groups:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_edit_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Text", callback_data=f"groups:schedule_text:{chat_id}")],
            [InlineKeyboardButton(text="⏱ Interval", callback_data=f"groups:schedule_interval:{chat_id}")],
            [InlineKeyboardButton(text="🟢 Yoqish", callback_data=f"groups:schedule_on:{chat_id}")],
            [InlineKeyboardButton(text="🔴 O‘chirish", callback_data=f"groups:schedule_off:{chat_id}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="groups:schedule")],
        ]
    )
