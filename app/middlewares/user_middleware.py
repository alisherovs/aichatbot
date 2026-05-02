from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update, User as TgUser
from app.config import get_settings
from app.database.repositories import UserRepository
from app.database.session import async_session_maker
from app.keyboards.legal import legal_consent_keyboard
from app.keyboards.subscription import required_subscription_keyboard
from app.services.legal_texts import LEGAL_CONSENT_TEXT
from app.services.subscription_service import check_required_subscriptions, required_subscription_text


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)
        async with async_session_maker() as session:
            repo = UserRepository(session)
            db_user = await repo.get_or_create_from_telegram(tg_user)
            if db_user.is_banned:
                await session.commit()
                bot = data.get("bot")
                if bot:
                    await bot.send_message(tg_user.id, "🚫 Sizning accountingiz bloklangan.")
                return None
            bot = data.get("bot")
            settings = get_settings()
            message, callback = _extract_user_event(event)
            is_force_check = callback is not None and callback.data == "force_sub:check"
            is_legal_callback = callback is not None and callback.data in {"legal:consent", "legal:terms", "legal:privacy", "legal:accept"}
            if bot and settings.required_subscription_items and not is_force_check:
                check = await check_required_subscriptions(bot, db_user.telegram_id)
                if not check.ok:
                    await session.commit()
                    text = required_subscription_text(check.missing)
                    keyboard = required_subscription_keyboard(check.missing)
                    if callback:
                        await callback.answer("Avval majburiy obunani bajaring.", show_alert=True)
                        if callback.message:
                            await callback.message.answer(text, reply_markup=keyboard)
                    elif message:
                        await message.answer(text, reply_markup=keyboard)
                    return None
            if bot and not db_user.legal_accepted_at and not is_legal_callback and not is_force_check:
                await session.commit()
                if callback:
                    await callback.answer("Avval shartlarga rozilik bering.", show_alert=True)
                    if callback.message:
                        await callback.message.answer(LEGAL_CONSENT_TEXT, reply_markup=legal_consent_keyboard())
                elif message:
                    await message.answer(LEGAL_CONSENT_TEXT, reply_markup=legal_consent_keyboard())
                return None
            data["session"] = session
            data["db_user"] = db_user
            result = await handler(event, data)
            await session.commit()
            return result


def _extract_user_event(event: TelegramObject) -> tuple[Message | None, CallbackQuery | None]:
    if isinstance(event, Message):
        return event, None
    if isinstance(event, CallbackQuery):
        return None, event
    if isinstance(event, Update):
        return event.message, event.callback_query
    return None, None
