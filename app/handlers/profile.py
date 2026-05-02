from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AutoreplyLog, User
from app.database.repositories import LinkedGroupRepository, TelegramAccountRepository
from app.keyboards.account import account_link_warning_keyboard, auth_code_keyboard, code_text
from app.keyboards.autoreply import autoreply_menu_keyboard
from app.keyboards.groups import (
    group_list_keyboard,
    groups_menu_keyboard,
    schedule_edit_keyboard,
    schedule_groups_keyboard,
    selected_groups_keyboard,
)
from app.keyboards.profile import profile_back_keyboard, profile_keyboard
from app.services.telegram_account.auth_service import (
    TelegramAuthError,
    TelegramTwoFactorRequired,
    confirm_2fa_password,
    confirm_code,
    start_login,
    unlink_account,
)
from app.services.telegram_account.client_manager import list_user_groups, send_manual_reply, start_user_client, stop_user_client
from app.services.telegram_account.session_service import SessionSecurityError
from app.services.usage_service import consume_ai_credit, get_remaining_credits, reset_daily_usage_if_needed
from app.services.persona_service import get_persona_title
from app.states.account_states import AccountLinkStates, AutoreplyStates, GroupLinkStates
from app.utils.formatting import fmt_dt
from app.utils.security import safe_html

router = Router()


async def safe_edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


def profile_text(user: User) -> str:
    reset_daily_usage_if_needed(user)
    name = " ".join(filter(None, [user.first_name, user.last_name])) or "-"
    username = f"@{safe_html(user.username)}" if user.username else "-"
    linked = "Ulangan" if user.is_account_linked else "Ulanmagan"
    premium_until = fmt_dt(user.premium_until) if user.premium_until else "Free tarif"
    persona_title = get_persona_title(user.selected_persona)
    remaining = get_remaining_credits(user)
    used = int(user.used_today or 0)
    limit = max(1, int(user.daily_limit or 1))
    percent = min(100, round((used / limit) * 100))
    plan_badges = {
        "free": "Boshlang‘ich",
        "pro": "Premium",
        "business": "Business",
    }
    account_status = "✅" if user.is_account_linked else "⚪️"
    return (
        "👤 <b>Profilim</b>\n"
        "TeleMind accountingiz va AI sozlamalaringiz.\n\n"
        "┌ <b>Account</b>\n"
        f"├ Ism: <b>{safe_html(name)}</b>\n"
        f"├ Username: <b>{username}</b>\n"
        f"└ Telegram ID: <code>{user.telegram_id}</code>\n\n"
        "┌ <b>Tarif va limit</b>\n"
        f"├ Tarif: <b>{safe_html(user.plan.title())}</b> · {plan_badges.get(user.plan, 'Faol')}\n"
        f"├ Bugungi sarf: <b>{used}/{user.daily_limit}</b> ({percent}%)\n"
        f"├ Qolgan javoblar: <b>{remaining}</b>\n"
        f"├ Bonus kreditlar: <b>{user.bonus_credits}</b>\n"
        f"└ Premium muddati: <b>{premium_until}</b>\n\n"
        "┌ <b>AI sozlamalar</b>\n"
        f"├ Personaj: <b>{persona_title}</b>\n"
        f"├ Telegram account: <b>{account_status} {linked}</b>\n"
        f"└ AI provider: <b>{safe_html(user.preferred_ai_provider.upper())}</b>\n\n"
        "Kerakli sozlamani pastdagi tugmalardan tanlang."
    )


@router.callback_query(F.data == "main:profile")
async def profile_menu(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.clear()
    await safe_edit(callback, profile_text(db_user), reply_markup=profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "account:link")
async def account_link_warning(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(
        callback,
        "<b>🔗 Account ulash</b>\n\n"
        "Bu funksiya Telegram accountingizni AI yordamchi bilan ulaydi. Kod, parol va session xavfsiz qayta ishlanadi. "
        "Siz istalgan vaqtda accountni uzishingiz mumkin.\n\n"
        "AI faqat sizga kelgan shaxsiy xabarlarga javob beradi. Ommaviy xabar yuborish yoki spam qilish funksiyasi yo‘q.",
        reply_markup=account_link_warning_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "account:confirm_link")
async def ask_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AccountLinkStates.waiting_for_phone)
    await safe_edit(
        callback,
        "<b>📱 Telefon raqam</b>\n\nTelegram accountingiz telefon raqamini xalqaro formatda yuboring.\n\nMasalan: <code>+998901234567</code>",
        reply_markup=profile_back_keyboard(),
    )
    await callback.answer()


@router.message(AccountLinkStates.waiting_for_phone, F.text)
async def receive_phone(message: Message, state: FSMContext, db_user: User) -> None:
    phone = message.text.strip().replace(" ", "")
    try:
        await start_login(db_user.id, phone)
    except (TelegramAuthError, SessionSecurityError) as exc:
        await message.answer(f"⚠️ {safe_html(exc)}", reply_markup=profile_back_keyboard())
        return
    await state.set_state(AccountLinkStates.waiting_for_code)
    await state.update_data(auth_code="")
    await message.answer(
        "<b>🔐 Telegram kodi yuborildi</b>\n\n" + code_text(""),
        reply_markup=auth_code_keyboard(),
    )


@router.message(AccountLinkStates.waiting_for_code)
async def reject_typed_code(message: Message) -> None:
    await message.answer(
        "Kod oddiy xabar bilan qabul qilinmaydi. Iltimos, Telegramdan kelgan kodni tugmalar orqali kiriting.",
        reply_markup=auth_code_keyboard(),
    )


@router.callback_query(AccountLinkStates.waiting_for_code, F.data.startswith("auth_digit:"))
async def auth_digit(callback: CallbackQuery, state: FSMContext) -> None:
    digit = callback.data.split(":", 1)[1]
    data = await state.get_data()
    code = (data.get("auth_code") or "")[:5]
    if len(code) < 5:
        code += digit
    await state.update_data(auth_code=code)
    await safe_edit(callback, "<b>🔐 Telegram kodi</b>\n\n" + code_text(code), reply_markup=auth_code_keyboard())
    await callback.answer()


@router.callback_query(AccountLinkStates.waiting_for_code, F.data == "auth_delete")
async def auth_delete(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    code = (data.get("auth_code") or "")[:-1]
    await state.update_data(auth_code=code)
    await safe_edit(callback, "<b>🔐 Telegram kodi</b>\n\n" + code_text(code), reply_markup=auth_code_keyboard())
    await callback.answer()


@router.callback_query(AccountLinkStates.waiting_for_code, F.data == "auth_confirm")
async def auth_confirm(callback: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    data = await state.get_data()
    code = data.get("auth_code") or ""
    if len(code) < 5:
        await callback.answer("Kod to‘liq kiritilmadi. Iltimos, Telegramdan kelgan kodni tugmalar orqali kiriting.", show_alert=True)
        return
    try:
        await confirm_code(session, db_user.id, code)
    except TelegramTwoFactorRequired:
        await state.set_state(AccountLinkStates.waiting_for_2fa_password)
        await safe_edit(callback, "<b>🔒 2FA parol kerak</b>\n\nTelegram ikki bosqichli parolini yuboring. Parol saqlanmaydi.")
        await callback.answer()
        return
    except (TelegramAuthError, SessionSecurityError) as exc:
        text = str(exc)
        if "muddati" in text:
            text = "Kod muddati tugagan. Iltimos, account ulashni qaytadan boshlang."
        elif "noto‘g‘ri" in text:
            text = "Kod noto‘g‘ri. Iltimos, qayta tekshirib kiriting."
        await callback.answer(text, show_alert=True)
        return
    db_user.is_account_linked = True
    await state.clear()
    await session.commit()
    try:
        await start_user_client(db_user.id, callback.bot)
    except Exception:
        pass
    await safe_edit(
        callback,
        "✅ Account muvaffaqiyatli ulandi. Endi AI yordamchini yoqib, shaxsiy xabarlarga yordamchi orqali javob berishni sozlashingiz mumkin.",
        reply_markup=profile_keyboard(),
    )
    await callback.answer()


@router.message(AccountLinkStates.waiting_for_2fa_password, F.text)
async def receive_2fa_password(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    password = message.text
    try:
        await message.delete()
    except Exception:
        pass
    try:
        await confirm_2fa_password(session, db_user.id, password)
    except (TelegramAuthError, SessionSecurityError) as exc:
        await message.answer(f"⚠️ {safe_html(exc)}", reply_markup=profile_back_keyboard())
        return
    db_user.is_account_linked = True
    await state.clear()
    await session.commit()
    try:
        await start_user_client(db_user.id, message.bot)
    except Exception:
        pass
    await message.answer(
        "✅ Account muvaffaqiyatli ulandi. 2FA parol saqlanmadi. Endi AI yordamchini yoqishingiz mumkin.",
        reply_markup=profile_keyboard(),
    )


@router.callback_query(F.data == "account:unlink")
async def account_unlink(callback: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    await stop_user_client(db_user.id)
    await unlink_account(session, db_user.id)
    db_user.is_account_linked = False
    await state.clear()
    await safe_edit(callback, "🔓 Account uzildi. Session ma’lumotlari o‘chirildi.", reply_markup=profile_keyboard())
    await callback.answer("Uzildi")


def autoreply_text(db_user: User, settings) -> str:
    status = "Yoqilgan" if settings.enabled else "O‘chirilgan"
    mode_names = {
        "off": "O‘chirilgan",
        "assistant_only": "Faqat tanishtirish",
        "auto": "Avtomatik javob",
        "confirm": "Avval tasdiqlatish",
    }
    away = "Ha" if settings.reply_only_when_away else "Yo‘q"
    linked = "Ha" if db_user.is_account_linked else "Yo‘q"
    return (
        "<b>💬 AI yordamchi</b>\n\n"
        f"Account ulangan: <b>{linked}</b>\n"
        f"Holat: <b>{status}</b>\n"
        f"Rejim: <b>{mode_names.get(settings.mode, settings.mode)}</b>\n"
        f"Faqat band bo‘lsam: <b>{away}</b>\n\n"
        "Yordamchi faqat kiruvchi shaxsiy xabarlarga javob beradi."
    )


@router.callback_query(F.data == "autoreply:menu")
async def autoreply_menu(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    settings = await TelegramAccountRepository(session).get_settings(db_user.id)
    await safe_edit(callback, autoreply_text(db_user, settings), reply_markup=autoreply_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "autoreply:on")
async def autoreply_on(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not db_user.is_account_linked:
        await callback.answer("Avval Telegram accountingizni ulang.", show_alert=True)
        return
    try:
        await start_user_client(db_user.id, callback.bot)
    except Exception as exc:
        await safe_edit(callback, f"⚠️ {safe_html(exc)}", reply_markup=profile_back_keyboard())
        await callback.answer()
        return
    repo = TelegramAccountRepository(session)
    await repo.set_autoreply_enabled(db_user.id, True)
    settings = await repo.get_settings(db_user.id)
    await safe_edit(callback, autoreply_text(db_user, settings), reply_markup=autoreply_menu_keyboard())
    await callback.answer("Yoqildi")


@router.callback_query(F.data == "autoreply:off")
async def autoreply_off(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    repo = TelegramAccountRepository(session)
    await repo.set_autoreply_enabled(db_user.id, False)
    await repo.set_autoreply_mode(db_user.id, "off")
    settings = await repo.get_settings(db_user.id)
    await safe_edit(callback, autoreply_text(db_user, settings), reply_markup=autoreply_menu_keyboard())
    await callback.answer("O‘chirildi")


@router.callback_query(F.data.in_(["autoreply:assistant_only", "autoreply:auto", "autoreply:confirm"]))
async def autoreply_set_mode(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    if not db_user.is_account_linked:
        await callback.answer("Avval Telegram accountingizni ulang.", show_alert=True)
        return
    mode = callback.data.split(":", 1)[1]
    repo = TelegramAccountRepository(session)
    await repo.set_autoreply_mode(db_user.id, mode)
    settings = await repo.get_settings(db_user.id)
    await safe_edit(callback, autoreply_text(db_user, settings), reply_markup=autoreply_menu_keyboard())
    await callback.answer("Saqlandi")


@router.callback_query(F.data == "autoreply:away_only")
async def autoreply_toggle_away(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    repo = TelegramAccountRepository(session)
    settings = await repo.get_settings(db_user.id)
    await repo.set_reply_only_when_away(db_user.id, not settings.reply_only_when_away)
    settings = await repo.get_settings(db_user.id)
    await safe_edit(callback, autoreply_text(db_user, settings), reply_markup=autoreply_menu_keyboard())
    await callback.answer("Saqlandi")


@router.callback_query(F.data == "autoreply:history")
async def autoreply_history(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    rows = await session.execute(
        select(AutoreplyLog)
        .where(AutoreplyLog.user_id == db_user.id)
        .order_by(AutoreplyLog.created_at.desc())
        .limit(5)
    )
    logs = rows.scalars().all()
    if not logs:
        text = "<b>📊 Javoblar tarixi</b>\n\nHozircha javoblar tarixi yo‘q."
    else:
        parts = ["<b>📊 Javoblar tarixi</b>"]
        for item in logs:
            parts.append(
                f"\n<b>{safe_html(item.peer_name or str(item.peer_id))}</b>\n"
                f"Holat: {safe_html(item.status)}\n"
                f"Xabar: {safe_html((item.incoming_text or '')[:120])}\n"
                f"Javob: {safe_html((item.ai_reply or '-')[:120])}"
            )
        text = "\n".join(parts)
    await safe_edit(callback, text, reply_markup=profile_back_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("draft:send:"))
async def draft_send(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    log_id = int(callback.data.rsplit(":", 1)[1])
    repo = TelegramAccountRepository(session)
    log = await repo.get_log(log_id)
    if log is None or log.user_id != db_user.id or not log.ai_reply:
        await callback.answer("Loyiha topilmadi.", show_alert=True)
        return
    try:
        await send_manual_reply(db_user.id, log.peer_id, log.ai_reply)
    except Exception as exc:
        await repo.update_log_status(log_id, "failed")
        await safe_edit(callback, f"⚠️ Javob yuborilmadi: {safe_html(exc)}", reply_markup=profile_back_keyboard())
        await callback.answer()
        return
    await repo.update_log_status(log_id, "sent")
    settings = await repo.get_settings(db_user.id)
    await repo.consume_autoreply_credit(settings)
    consume_ai_credit(db_user)
    await safe_edit(callback, "<b>✅ Javob yuborildi</b>", reply_markup=profile_back_keyboard())
    await callback.answer("Yuborildi")


@router.callback_query(F.data.startswith("draft:cancel:"))
async def draft_cancel(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    log_id = int(callback.data.rsplit(":", 1)[1])
    repo = TelegramAccountRepository(session)
    log = await repo.get_log(log_id)
    if log is None or log.user_id != db_user.id:
        await callback.answer("Loyiha topilmadi.", show_alert=True)
        return
    await repo.update_log_status(log_id, "skipped")
    await safe_edit(callback, "<b>❌ Javob bekor qilindi</b>", reply_markup=profile_back_keyboard())
    await callback.answer("Bekor qilindi")


@router.callback_query(F.data.startswith("draft:edit:"))
async def draft_edit(callback: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    log_id = int(callback.data.rsplit(":", 1)[1])
    log = await TelegramAccountRepository(session).get_log(log_id)
    if log is None or log.user_id != db_user.id:
        await callback.answer("Loyiha topilmadi.", show_alert=True)
        return
    await state.set_state(AutoreplyStates.waiting_for_draft_edit)
    await state.update_data(log_id=log_id)
    await safe_edit(callback, "<b>✏️ Javobni tahrirlash</b>\n\nYuboriladigan yangi matnni yozing.", reply_markup=profile_back_keyboard())
    await callback.answer()


@router.message(AutoreplyStates.waiting_for_draft_edit, F.text)
async def draft_edit_save(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    data = await state.get_data()
    log_id = int(data.get("log_id"))
    repo = TelegramAccountRepository(session)
    log = await repo.get_log(log_id)
    if log is None or log.user_id != db_user.id:
        await message.answer("Loyiha topilmadi.", reply_markup=profile_back_keyboard())
        await state.clear()
        return
    try:
        await send_manual_reply(db_user.id, log.peer_id, message.text)
    except Exception as exc:
        await repo.update_log_status(log_id, "failed", message.text)
        await message.answer(f"⚠️ Javob yuborilmadi: {safe_html(exc)}", reply_markup=profile_back_keyboard())
        await state.clear()
        return
    await repo.update_log_status(log_id, "sent", message.text)
    settings = await repo.get_settings(db_user.id)
    await repo.consume_autoreply_credit(settings)
    consume_ai_credit(db_user)
    await state.clear()
    await message.answer("<b>✅ Tahrirlangan javob yuborildi</b>", reply_markup=profile_back_keyboard())


def groups_text(db_user: User, groups_count: int) -> str:
    linked = "Ha" if db_user.is_account_linked else "Yo‘q"
    return (
        "<b>👥 Guruh bog‘lash</b>\n\n"
        f"Account ulangan: <b>{linked}</b>\n"
        f"Tanlangan guruhlar: <b>{groups_count}</b>\n\n"
        "Tanlangan guruhlarda sizga reply qilinsa yoki @username bilan metka qilinsa AI avtomatik javob beradi. "
        "Timer esa belgilangan textni tanlangan guruhlarga berilgan intervalda yuboradi."
    )


@router.callback_query(F.data == "groups:menu")
async def groups_menu(callback: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    await state.clear()
    count = len(await LinkedGroupRepository(session).list_active(db_user.id))
    await safe_edit(callback, groups_text(db_user, count), reply_markup=groups_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("groups:list:"))
async def groups_list(callback: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    if not db_user.is_account_linked:
        await callback.answer("Avval Telegram accountingizni ulang.", show_alert=True)
        return
    page = int(callback.data.rsplit(":", 1)[1])
    try:
        groups = await list_user_groups(db_user.id)
    except Exception as exc:
        await safe_edit(callback, f"⚠️ Guruhlar olinmadi: {safe_html(exc)}", reply_markup=groups_menu_keyboard())
        await callback.answer()
        return
    await state.update_data(available_groups=groups)
    selected = {item.chat_id for item in await LinkedGroupRepository(session).list_active(db_user.id)}
    text = "<b>➕ Guruh tanlash</b>\n\nGuruhni bosib tanlang yoki tanlovdan chiqaring."
    await safe_edit(callback, text, reply_markup=group_list_keyboard(groups, selected, page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("groups:toggle:"))
async def groups_toggle(callback: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    chat_id = int(parts[2])
    page = int(parts[3])
    data = await state.get_data()
    groups = data.get("available_groups") or []
    group_info = next((item for item in groups if int(item["id"]) == chat_id), None)
    repo = LinkedGroupRepository(session)
    if await repo.is_selected(db_user.id, chat_id):
        await repo.deactivate(db_user.id, chat_id)
        await callback.answer("Tanlovdan olindi")
    else:
        await repo.upsert(
            db_user.id,
            chat_id,
            (group_info or {}).get("title") or str(chat_id),
            (group_info or {}).get("username"),
        )
        await callback.answer("Guruh bog‘landi")
    await session.commit()
    selected = {item.chat_id for item in await repo.list_active(db_user.id)}
    await safe_edit(callback, "<b>➕ Guruh tanlash</b>\n\nGuruhni bosib tanlang yoki tanlovdan chiqaring.", reply_markup=group_list_keyboard(groups, selected, page=page))


@router.callback_query(F.data == "groups:selected")
async def groups_selected(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    groups = await LinkedGroupRepository(session).list_active(db_user.id)
    if not groups:
        text = "<b>📋 Bog‘langan guruhlar</b>\n\nHozircha guruh tanlanmagan."
    else:
        lines = ["<b>📋 Bog‘langan guruhlar</b>"]
        for group in groups:
            timer = "yoqilgan" if group.schedule_enabled else "o‘chirilgan"
            lines.append(f"\n<b>{safe_html(group.title or str(group.chat_id))}</b>\nTimer: {timer}")
        text = "\n".join(lines)
    await safe_edit(callback, text, reply_markup=selected_groups_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data.startswith("groups:remove:"))
async def groups_remove(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    chat_id = int(callback.data.rsplit(":", 1)[1])
    repo = LinkedGroupRepository(session)
    await repo.deactivate(db_user.id, chat_id)
    await session.commit()
    groups = await repo.list_active(db_user.id)
    await safe_edit(callback, "<b>📋 Bog‘langan guruhlar</b>\n\nGuruh tanlovdan olindi.", reply_markup=selected_groups_keyboard(groups))
    await callback.answer("Olib tashlandi")


@router.callback_query(F.data == "groups:schedule")
async def groups_schedule(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    groups = await LinkedGroupRepository(session).list_active(db_user.id)
    text = "<b>⏱ Timer sozlash</b>\n\nTimer sozlanadigan guruhni tanlang." if groups else "<b>⏱ Timer sozlash</b>\n\nAvval guruh tanlang."
    await safe_edit(callback, text, reply_markup=schedule_groups_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data.startswith("groups:schedule_group:"))
async def groups_schedule_group(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    chat_id = int(callback.data.rsplit(":", 1)[1])
    rendered = await render_schedule_group(callback, db_user, session, chat_id)
    if rendered:
        await callback.answer()


async def render_schedule_group(callback: CallbackQuery, db_user: User, session: AsyncSession, chat_id: int) -> bool:
    group = await LinkedGroupRepository(session).get(db_user.id, chat_id)
    if group is None or not group.is_active:
        await callback.answer("Guruh topilmadi.", show_alert=True)
        return False
    status = "Yoqilgan" if group.schedule_enabled else "O‘chirilgan"
    text = (
        f"<b>⏱ {safe_html(group.title or str(group.chat_id))}</b>\n\n"
        f"Holat: <b>{status}</b>\n"
        f"Interval: <b>{group.schedule_interval_minutes} daqiqa</b>\n"
        f"Text: {safe_html((group.schedule_text or '-')[:800])}"
    )
    await safe_edit(callback, text, reply_markup=schedule_edit_keyboard(chat_id))
    return True


@router.callback_query(F.data.startswith("groups:schedule_text:"))
async def groups_ask_schedule_text(callback: CallbackQuery, state: FSMContext) -> None:
    chat_id = int(callback.data.rsplit(":", 1)[1])
    await state.set_state(GroupLinkStates.waiting_for_schedule_text)
    await state.update_data(schedule_chat_id=chat_id)
    await safe_edit(callback, "<b>✍️ Timer text</b>\n\nGuruhga interval bo‘yicha yuboriladigan matnni yozing.", reply_markup=profile_back_keyboard())
    await callback.answer()


@router.message(GroupLinkStates.waiting_for_schedule_text, F.text)
async def groups_save_schedule_text(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    data = await state.get_data()
    chat_id = int(data.get("schedule_chat_id"))
    group = await LinkedGroupRepository(session).get(db_user.id, chat_id)
    if group is None or not group.is_active:
        await message.answer("Guruh topilmadi.", reply_markup=profile_back_keyboard())
        await state.clear()
        return
    group.schedule_text = message.text.strip()
    await session.commit()
    await state.clear()
    await message.answer("✅ Timer text saqlandi.", reply_markup=schedule_edit_keyboard(chat_id))


@router.callback_query(F.data.startswith("groups:schedule_interval:"))
async def groups_ask_schedule_interval(callback: CallbackQuery, state: FSMContext) -> None:
    chat_id = int(callback.data.rsplit(":", 1)[1])
    await state.set_state(GroupLinkStates.waiting_for_schedule_interval)
    await state.update_data(schedule_chat_id=chat_id)
    await safe_edit(callback, "<b>⏱ Interval</b>\n\nNecha daqiqada bir yuborilsin? Masalan: <code>60</code>", reply_markup=profile_back_keyboard())
    await callback.answer()


@router.message(GroupLinkStates.waiting_for_schedule_interval, F.text)
async def groups_save_schedule_interval(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) < 1:
        await message.answer("Interval kamida 1 daqiqa bo‘lishi kerak. Faqat raqam yuboring.")
        return
    data = await state.get_data()
    chat_id = int(data.get("schedule_chat_id"))
    group = await LinkedGroupRepository(session).get(db_user.id, chat_id)
    if group is None or not group.is_active:
        await message.answer("Guruh topilmadi.", reply_markup=profile_back_keyboard())
        await state.clear()
        return
    group.schedule_interval_minutes = min(int(raw), 43200)
    if group.schedule_enabled:
        group.schedule_next_run_at = datetime.utcnow() + timedelta(minutes=group.schedule_interval_minutes)
    await session.commit()
    await state.clear()
    await message.answer("✅ Timer interval saqlandi.", reply_markup=schedule_edit_keyboard(chat_id))


@router.callback_query(F.data.startswith("groups:schedule_on:"))
async def groups_schedule_on(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    chat_id = int(callback.data.rsplit(":", 1)[1])
    group = await LinkedGroupRepository(session).get(db_user.id, chat_id)
    if group is None or not group.is_active:
        await callback.answer("Guruh topilmadi.", show_alert=True)
        return
    if not (group.schedule_text or "").strip():
        await callback.answer("Avval timer text kiriting.", show_alert=True)
        return
    group.schedule_enabled = True
    group.schedule_next_run_at = datetime.utcnow() + timedelta(minutes=max(1, group.schedule_interval_minutes or 60))
    await session.commit()
    await render_schedule_group(callback, db_user, session, chat_id)
    await callback.answer("Timer yoqildi")


@router.callback_query(F.data.startswith("groups:schedule_off:"))
async def groups_schedule_off(callback: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    chat_id = int(callback.data.rsplit(":", 1)[1])
    group = await LinkedGroupRepository(session).get(db_user.id, chat_id)
    if group is None or not group.is_active:
        await callback.answer("Guruh topilmadi.", show_alert=True)
        return
    group.schedule_enabled = False
    await session.commit()
    await render_schedule_group(callback, db_user, session, chat_id)
    await callback.answer("Timer o‘chirildi")
