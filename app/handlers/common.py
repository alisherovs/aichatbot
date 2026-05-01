import logging
from datetime import datetime
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message
from app.database.models import User
from app.keyboards.legal import legal_consent_keyboard, legal_document_keyboard
from app.keyboards.main_menu import help_keyboard, main_menu
from app.keyboards.subscription import required_subscription_keyboard
from app.services.legal_texts import LEGAL_CONSENT_TEXT, PRIVACY_TEXT, TERMS_TEXT
from app.services.subscription_service import check_required_subscriptions, required_subscription_text
from app.utils.telegram import is_message_not_modified_error, safe_edit_text

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.in_({"back:main", "back:menu"}))
async def back_to_main(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.clear()
    await safe_edit_text(
        callback.message,
        "<b>🤖 TeleMind AI</b>\n\nAsosiy menyu:",
        reply_markup=main_menu(db_user.role == "admin"),
    )
    await callback.answer()


@router.callback_query(F.data == "force_sub:check")
async def check_force_subscription(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    check = await check_required_subscriptions(callback.bot, db_user.telegram_id)
    if not check.ok:
        await callback.answer("Hali hamma joyga obuna bo‘lmadingiz.", show_alert=True)
        await safe_edit_text(
            callback.message,
            required_subscription_text(check.missing),
            reply_markup=required_subscription_keyboard(check.missing),
        )
        return
    await state.clear()
    await safe_edit_text(
        callback.message,
        LEGAL_CONSENT_TEXT if not db_user.legal_accepted_at else "<b>✅ Obuna tasdiqlandi</b>\n\n<b>🤖 TeleMind AI</b>\n\nAsosiy menyu:",
        reply_markup=legal_consent_keyboard() if not db_user.legal_accepted_at else main_menu(db_user.role == "admin"),
    )
    await callback.answer("Obuna tasdiqlandi")


@router.callback_query(F.data == "legal:consent")
async def legal_consent(callback: CallbackQuery) -> None:
    await safe_edit_text(callback.message, LEGAL_CONSENT_TEXT, reply_markup=legal_consent_keyboard())
    await callback.answer()


@router.callback_query(F.data == "legal:terms")
async def legal_terms(callback: CallbackQuery) -> None:
    await safe_edit_text(callback.message, TERMS_TEXT, reply_markup=legal_document_keyboard())
    await callback.answer()


@router.callback_query(F.data == "legal:privacy")
async def legal_privacy(callback: CallbackQuery) -> None:
    await safe_edit_text(callback.message, PRIVACY_TEXT, reply_markup=legal_document_keyboard())
    await callback.answer()


@router.callback_query(F.data == "legal:accept")
async def legal_accept(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    db_user.legal_accepted_at = datetime.utcnow()
    await state.clear()
    await safe_edit_text(
        callback.message,
        "<b>✅ Rozilik qabul qilindi</b>\n\n<b>🤖 TeleMind AI</b>\n\nAsosiy menyu:",
        reply_markup=main_menu(db_user.role == "admin"),
    )
    await callback.answer("Rozilik saqlandi")


@router.callback_query(F.data == "main:help")
async def help_menu(callback: CallbackQuery) -> None:
    await safe_edit_text(
        callback.message,
        "<b>❓ Yordam</b>\n\n"
        "Bu bot AI suhbat, personajlar, AI vositalar, doimiy prompt, Telegram account ulash, shaxsiy xabarlarga AI yordamchi va Premium tariflarni qo‘llab-quvvatlaydi.\n\n"
        "Savol yozish uchun <b>AI bilan suhbat</b> bo‘limiga kiring.",
        reply_markup=help_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "main:terms")
async def terms_menu(callback: CallbackQuery) -> None:
    await safe_edit_text(callback.message, TERMS_TEXT, reply_markup=help_keyboard())
    await callback.answer()


@router.callback_query(F.data == "main:privacy")
async def privacy_menu(callback: CallbackQuery) -> None:
    await safe_edit_text(callback.message, PRIVACY_TEXT, reply_markup=help_keyboard())
    await callback.answer()


@router.error()
async def errors_handler(event: ErrorEvent) -> None:
    if is_message_not_modified_error(event.exception):
        return
    logger.exception("Unhandled update error", exc_info=event.exception)


@router.message()
async def fallback_message(message: Message) -> None:
    await message.answer("Menyudan bo‘lim tanlang yoki /start buyrug‘ini yuboring.")
