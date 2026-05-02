from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
                InlineKeyboardButton(text="👤 Userlar", callback_data="admin:users"),
            ],
            [
                InlineKeyboardButton(text="💎 Tarif berish", callback_data="admin:grant_plan"),
                InlineKeyboardButton(text="🎟 Promokodlar", callback_data="admin:promos"),
            ],
            [
                InlineKeyboardButton(text="💰 To‘lovlar", callback_data="admin:payments"),
                InlineKeyboardButton(text="🎁 Bonus berish", callback_data="admin:bonus"),
            ],
            [
                InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin:broadcast"),
                InlineKeyboardButton(text="🚫 Bloklash", callback_data="admin:ban"),
            ],
            [InlineKeyboardButton(text="🧾 Loglar", callback_data="admin:logs")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:main")],
        ]
    )


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")]])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="admin:broadcast_confirm")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:panel")],
        ]
    )


def admin_plan_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Free", callback_data=f"admin:grant:free:{telegram_id}"),
                InlineKeyboardButton(text="Pro", callback_data=f"admin:grant:pro:{telegram_id}"),
            ],
            [InlineKeyboardButton(text="Business", callback_data=f"admin:grant:business:{telegram_id}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")],
        ]
    )


def admin_grant_users_keyboard(users: list) -> InlineKeyboardMarkup:
    rows = []
    for user in users[:10]:
        name = " ".join(part for part in [user.first_name, user.last_name] if part) or user.username or str(user.telegram_id)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"👤 {name[:24]} · {user.plan.title()}",
                    callback_data=f"admin:grant_user:{user.telegram_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔎 ID orqali topish", callback_data="admin:grant_manual")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Kredit promokod", callback_data="admin:promo_create_credits"),
                InlineKeyboardButton(text="💎 Tarif promokod", callback_data="admin:promo_create_plan"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")],
        ]
    )


def promo_credit_amount_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="10 kredit", callback_data="admin:promo_credit_amount:10"),
                InlineKeyboardButton(text="25 kredit", callback_data="admin:promo_credit_amount:25"),
            ],
            [
                InlineKeyboardButton(text="50 kredit", callback_data="admin:promo_credit_amount:50"),
                InlineKeyboardButton(text="100 kredit", callback_data="admin:promo_credit_amount:100"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:promos")],
        ]
    )


def promo_plan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Pro", callback_data="admin:promo_plan_type:pro"),
                InlineKeyboardButton(text="Business", callback_data="admin:promo_plan_type:business"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:promos")],
        ]
    )


def promo_plan_days_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="7 kun", callback_data="admin:promo_plan_days:7"),
                InlineKeyboardButton(text="30 kun", callback_data="admin:promo_plan_days:30"),
            ],
            [
                InlineKeyboardButton(text="90 kun", callback_data="admin:promo_plan_days:90"),
                InlineKeyboardButton(text="365 kun", callback_data="admin:promo_plan_days:365"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:promos")],
        ]
    )


def promo_max_uses_keyboard(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 marta", callback_data=f"admin:promo_uses:{kind}:1"),
                InlineKeyboardButton(text="10 marta", callback_data=f"admin:promo_uses:{kind}:10"),
            ],
            [
                InlineKeyboardButton(text="50 marta", callback_data=f"admin:promo_uses:{kind}:50"),
                InlineKeyboardButton(text="100 marta", callback_data=f"admin:promo_uses:{kind}:100"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:promos")],
        ]
    )


def promo_valid_days_keyboard(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="7 kun", callback_data=f"admin:promo_valid:{kind}:7"),
                InlineKeyboardButton(text="30 kun", callback_data=f"admin:promo_valid:{kind}:30"),
            ],
            [
                InlineKeyboardButton(text="90 kun", callback_data=f"admin:promo_valid:{kind}:90"),
                InlineKeyboardButton(text="Muddatsiz", callback_data=f"admin:promo_valid:{kind}:0"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:promos")],
        ]
    )
