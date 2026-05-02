from __future__ import annotations

from datetime import date, datetime
from aiogram.types import User as TgUser
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    AIAutoreplySettings,
    AdminAction,
    AllowedChat,
    AutoreplyChatState,
    AutoreplyLog,
    BlockedChat,
    BonusTransaction,
    Conversation,
    LinkedGroup,
    MessageLog,
    Payment,
    PromoCode,
    PromoCodeRedemption,
    Referral,
    TelegramSession,
    UsageLog,
    User,
)
from app.services.usage_service import get_plan_limit
from app.utils.admin import is_admin


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get_or_create_from_telegram(self, tg_user: TgUser) -> User:
        user = await self.get_by_telegram_id(tg_user.id)
        role = "admin" if is_admin(tg_user.id) else "user"
        if user is None:
            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code,
                role=role,
                preferred_ai_provider="groq",
                selected_persona="bilimdon",
                daily_limit=get_plan_limit("free"),
                limit_reset_date=date.today(),
                last_active_at=datetime.utcnow(),
            )
            self.session.add(user)
        else:
            user.username = tg_user.username
            user.first_name = tg_user.first_name
            user.last_name = tg_user.last_name
            user.language_code = tg_user.language_code
            user.role = role
            user.preferred_ai_provider = "groq"
            if not user.selected_persona or user.selected_persona == "yordamchi":
                user.selected_persona = "bilimdon"
            if user.premium_until and user.premium_until < datetime.utcnow():
                user.plan = "free"
                user.daily_limit = get_plan_limit("free")
                user.used_today = 0
                user.premium_until = None
            if not user.daily_limit or user.daily_limit in {20, 1000, 2000}:
                user.daily_limit = get_plan_limit(user.plan)
            if getattr(user, "limit_reset_date", None) is None:
                user.limit_reset_date = date.today()
            user.last_active_at = datetime.utcnow()
        await self.session.flush()
        return user

    async def set_prompt(self, user_id: int, prompt: str | None) -> None:
        await self.session.execute(update(User).where(User.id == user_id).values(custom_prompt=prompt))

    async def link_account(self, user_id: int) -> None:
        await self.session.execute(update(User).where(User.id == user_id).values(is_account_linked=True))

    async def unlink_account(self, user_id: int) -> None:
        await self.session.execute(update(User).where(User.id == user_id).values(is_account_linked=False))

    async def increment_usage(self, user_id: int) -> None:
        await self.session.execute(update(User).where(User.id == user_id).values(used_today=User.used_today + 1))

    async def update_plan(self, telegram_id: int, plan: str) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        user.plan = plan
        user.daily_limit = get_plan_limit(plan)
        user.used_today = 0
        user.limit_reset_date = date.today()
        await self.session.flush()
        return user

    async def clear_memory(self, user_id: int) -> None:
        await self.session.execute(delete(MessageLog).where(MessageLog.user_id == user_id))
        await self.session.execute(delete(Conversation).where(Conversation.user_id == user_id))

    async def delete_user_data(self, user_id: int) -> None:
        await self.session.execute(delete(User).where(User.id == user_id))


class TelegramAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_session(self, user_id: int) -> TelegramSession | None:
        result = await self.session.execute(select(TelegramSession).where(TelegramSession.user_id == user_id))
        return result.scalar_one_or_none()

    async def save_session(self, user_id: int, phone: str, encrypted_session: str) -> TelegramSession:
        existing = await self.get_session(user_id)
        if existing:
            existing.phone = phone
            existing.encrypted_session = encrypted_session
            existing.is_active = True
            await self.session.flush()
            return existing
        item = TelegramSession(user_id=user_id, phone=phone, encrypted_session=encrypted_session, is_active=True)
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete_session(self, user_id: int) -> None:
        await self.session.execute(delete(TelegramSession).where(TelegramSession.user_id == user_id))

    async def get_settings(self, user_id: int) -> AIAutoreplySettings:
        result = await self.session.execute(select(AIAutoreplySettings).where(AIAutoreplySettings.user_id == user_id))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = AIAutoreplySettings(user_id=user_id)
            self.session.add(settings)
            await self.session.flush()
        return settings

    async def reset_autoreply_usage_if_needed(self, settings: AIAutoreplySettings) -> None:
        today = date.today()
        if settings.reset_date != today:
            settings.used_today = 0
            settings.reset_date = today

    async def consume_autoreply_credit(self, settings: AIAutoreplySettings) -> None:
        await self.reset_autoreply_usage_if_needed(settings)
        settings.used_today += 1

    async def set_autoreply_enabled(self, user_id: int, enabled: bool) -> None:
        settings = await self.get_settings(user_id)
        settings.enabled = enabled
        if enabled and settings.mode == "off":
            settings.mode = "assistant_only"

    async def set_autoreply_mode(self, user_id: int, mode: str) -> None:
        settings = await self.get_settings(user_id)
        settings.mode = mode
        settings.enabled = mode != "off"

    async def set_reply_only_when_away(self, user_id: int, value: bool) -> None:
        settings = await self.get_settings(user_id)
        settings.reply_only_when_away = value

    async def set_away_after_minutes(self, user_id: int, minutes: int) -> None:
        settings = await self.get_settings(user_id)
        settings.away_after_minutes = minutes

    async def log_autoreply(
        self,
        user_id: int,
        peer_id: int,
        peer_name: str | None,
        incoming_text: str,
        ai_reply: str | None,
        status: str,
        skipped_reason: str | None = None,
        provider: str | None = None,
        error_text: str | None = None,
        persona_key: str | None = None,
    ) -> AutoreplyLog:
        item = AutoreplyLog(
            user_id=user_id,
            incoming_chat_id=peer_id,
            incoming_user_id=peer_id,
            peer_id=peer_id,
            peer_name=peer_name,
            incoming_text=incoming_text,
            ai_reply=ai_reply,
            status=status,
            skipped_reason=skipped_reason,
            provider=provider,
            persona_key=persona_key,
            error_text=error_text,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_log(self, log_id: int) -> AutoreplyLog | None:
        result = await self.session.execute(select(AutoreplyLog).where(AutoreplyLog.id == log_id))
        return result.scalar_one_or_none()

    async def update_log_status(self, log_id: int, status: str, ai_reply: str | None = None) -> None:
        values = {"status": status}
        if ai_reply is not None:
            values["ai_reply"] = ai_reply
        await self.session.execute(update(AutoreplyLog).where(AutoreplyLog.id == log_id).values(**values))

    async def daily_reply_count(self, user_id: int) -> int:
        settings = await self.get_settings(user_id)
        await self.reset_autoreply_usage_if_needed(settings)
        return int(settings.used_today or 0)

    async def get_chat_state(self, user_id: int, peer_id: int, peer_name: str | None = None) -> AutoreplyChatState:
        result = await self.session.execute(
            select(AutoreplyChatState).where(AutoreplyChatState.user_id == user_id, AutoreplyChatState.peer_id == peer_id)
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = AutoreplyChatState(user_id=user_id, peer_id=peer_id, peer_name=peer_name)
            self.session.add(state)
            await self.session.flush()
        elif peer_name and state.peer_name != peer_name:
            state.peer_name = peer_name
        return state

    async def mark_incoming(self, user_id: int, peer_id: int, peer_name: str | None = None) -> AutoreplyChatState:
        state = await self.get_chat_state(user_id, peer_id, peer_name)
        state.last_incoming_at = datetime.utcnow()
        state.message_count += 1
        return state

    async def mark_intro_sent(self, user_id: int, peer_id: int) -> None:
        state = await self.get_chat_state(user_id, peer_id)
        state.intro_sent = True

    async def mark_reply_sent(self, user_id: int, peer_id: int) -> None:
        state = await self.get_chat_state(user_id, peer_id)
        state.last_reply_at = datetime.utcnow()

    async def mark_owner_outgoing(self, user_id: int, peer_id: int, peer_name: str | None = None) -> None:
        state = await self.get_chat_state(user_id, peer_id, peer_name)
        state.last_owner_outgoing_at = datetime.utcnow()

    async def is_blocked(self, user_id: int, chat_id: int) -> bool:
        result = await self.session.execute(
            select(BlockedChat.id).where(BlockedChat.user_id == user_id, BlockedChat.chat_id == chat_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def allowed_count(self, user_id: int) -> int:
        result = await self.session.execute(select(func.count(AllowedChat.id)).where(AllowedChat.user_id == user_id, AllowedChat.is_allowed.is_(True)))
        return int(result.scalar() or 0)

    async def is_allowed(self, user_id: int, chat_id: int) -> bool:
        result = await self.session.execute(
            select(AllowedChat.id).where(AllowedChat.user_id == user_id, AllowedChat.chat_id == chat_id, AllowedChat.is_allowed.is_(True)).limit(1)
        )
        return result.scalar_one_or_none() is not None


class LinkedGroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self, user_id: int) -> list[LinkedGroup]:
        result = await self.session.execute(
            select(LinkedGroup)
            .where(LinkedGroup.user_id == user_id, LinkedGroup.is_active.is_(True))
            .order_by(LinkedGroup.title.asc())
        )
        return list(result.scalars().all())

    async def get(self, user_id: int, chat_id: int) -> LinkedGroup | None:
        result = await self.session.execute(
            select(LinkedGroup).where(LinkedGroup.user_id == user_id, LinkedGroup.chat_id == chat_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: int, chat_id: int, title: str | None, username: str | None = None) -> LinkedGroup:
        group = await self.get(user_id, chat_id)
        if group is None:
            group = LinkedGroup(user_id=user_id, chat_id=chat_id, title=title, username=username, is_active=True)
            self.session.add(group)
        else:
            group.title = title or group.title
            group.username = username or group.username
            group.is_active = True
        await self.session.flush()
        return group

    async def deactivate(self, user_id: int, chat_id: int) -> None:
        group = await self.get(user_id, chat_id)
        if group:
            group.is_active = False

    async def is_selected(self, user_id: int, chat_id: int) -> bool:
        result = await self.session.execute(
            select(LinkedGroup.id)
            .where(LinkedGroup.user_id == user_id, LinkedGroup.chat_id == chat_id, LinkedGroup.is_active.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def due_schedules(self, user_id: int, now: datetime) -> list[LinkedGroup]:
        result = await self.session.execute(
            select(LinkedGroup).where(
                LinkedGroup.user_id == user_id,
                LinkedGroup.is_active.is_(True),
                LinkedGroup.schedule_enabled.is_(True),
                LinkedGroup.schedule_text.is_not(None),
                LinkedGroup.schedule_next_run_at <= now,
            )
        )
        return list(result.scalars().all())


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_active(self, user_id: int) -> Conversation:
        result = await self.session.execute(
            select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).limit(1)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            conversation = Conversation(user_id=user_id)
            self.session.add(conversation)
            await self.session.flush()
        return conversation

    async def add_message(
        self, user_id: int, conversation_id: int | None, role: str, content: str, tokens_used: int = 0
    ) -> MessageLog:
        msg = MessageLog(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def recent_messages(self, conversation_id: int, limit: int = 10) -> list[MessageLog]:
        result = await self.session.execute(
            select(MessageLog)
            .where(MessageLog.conversation_id == conversation_id)
            .order_by(MessageLog.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))


class UsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, user_id: int, action: str) -> None:
        self.session.add(UsageLog(user_id=user_id, action=action))


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_pending(self, user_id: int, telegram_id: int, plan: str, amount_stars: int, payload: str) -> Payment:
        payment = Payment(user_id=user_id, telegram_id=telegram_id, plan=plan, amount_stars=amount_stars, amount=amount_stars, status="pending", invoice_payload=payload)
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_by_payload(self, payload: str) -> Payment | None:
        result = await self.session.execute(select(Payment).where(Payment.invoice_payload == payload))
        return result.scalar_one_or_none()


class BonusRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_bonus(self, user: User, amount: int, source: str, admin_id: int | None = None, reason: str | None = None) -> BonusTransaction:
        user.bonus_credits = int(user.bonus_credits or 0) + amount
        item = BonusTransaction(user_id=user.id, admin_id=admin_id, amount=amount, source=source, reason=reason)
        self.session.add(item)
        await self.session.flush()
        return item


class PromoCodeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> PromoCode | None:
        normalized = code.strip().upper()
        result = await self.session.execute(select(PromoCode).where(PromoCode.code == normalized))
        return result.scalar_one_or_none()

    async def create(
        self,
        code: str,
        reward_type: str,
        created_by: int,
        credits: int = 0,
        plan: str | None = None,
        plan_days: int = 0,
        max_uses: int = 1,
        expires_at: datetime | None = None,
    ) -> PromoCode:
        item = PromoCode(
            code=code.strip().upper(),
            reward_type=reward_type,
            credits=credits,
            plan=plan,
            plan_days=plan_days,
            max_uses=max_uses,
            expires_at=expires_at,
            created_by=created_by,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def user_redeemed(self, user_id: int, promo_code_id: int) -> bool:
        result = await self.session.execute(
            select(PromoCodeRedemption.id)
            .where(PromoCodeRedemption.user_id == user_id, PromoCodeRedemption.promo_code_id == promo_code_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def redeem(self, user: User, promo: PromoCode) -> PromoCodeRedemption:
        if promo.reward_type == "credits":
            reward_value = str(promo.credits)
            await BonusRepository(self.session).add_bonus(user, promo.credits, "promo", reason=f"Promokod: {promo.code}")
        elif promo.reward_type == "plan":
            reward_value = f"{promo.plan}:{promo.plan_days}"
            user.plan = promo.plan or "free"
            user.daily_limit = get_plan_limit(user.plan)
            user.used_today = 0
            user.limit_reset_date = date.today()
            if promo.plan_days:
                from datetime import timedelta

                user.premium_until = datetime.utcnow() + timedelta(days=promo.plan_days)
        else:
            raise ValueError("Promokod turi noto‘g‘ri.")
        promo.used_count += 1
        item = PromoCodeRedemption(
            promo_code_id=promo.id,
            user_id=user.id,
            code=promo.code,
            reward_type=promo.reward_type,
            reward_value=reward_value,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def latest(self, limit: int = 10) -> list[PromoCode]:
        result = await self.session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()).limit(limit))
        return list(result.scalars().all())


class ReferralRepository:
    REFERRER_BONUS = 10
    REFERRED_BONUS = 5

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_referred(self, referred_id: int) -> Referral | None:
        result = await self.session.execute(select(Referral).where(Referral.referred_id == referred_id))
        return result.scalar_one_or_none()

    async def create_referral(self, referrer: User, referred: User) -> Referral | None:
        if referrer.id == referred.id or await self.get_for_referred(referred.id):
            return None
        item = Referral(
            referrer_id=referrer.id,
            referred_id=referred.id,
            referrer_bonus=self.REFERRER_BONUS,
            referred_bonus=self.REFERRED_BONUS,
        )
        self.session.add(item)
        bonus_repo = BonusRepository(self.session)
        await bonus_repo.add_bonus(referrer, self.REFERRER_BONUS, "referral", reason=f"Taklif qilingan user: {referred.telegram_id}")
        await bonus_repo.add_bonus(referred, self.REFERRED_BONUS, "referral", reason=f"Taklif qilgan user: {referrer.telegram_id}")
        await self.session.flush()
        return item

    async def stats_for_user(self, user_id: int) -> dict[str, int]:
        total = await self.session.scalar(select(func.count(Referral.id)).where(Referral.referrer_id == user_id))
        return {"total": int(total or 0), "referrer_bonus": self.REFERRER_BONUS, "referred_bonus": self.REFERRED_BONUS}


class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def stats(self) -> dict[str, int]:
        total_users = await self.session.scalar(select(func.count(User.id)))
        active_users = await self.session.scalar(select(func.count(User.id)).where(User.is_banned.is_(False)))
        premium_users = await self.session.scalar(select(func.count(User.id)).where(User.plan.in_(["pro", "business"])))
        linked_accounts = await self.session.scalar(select(func.count(User.id)).where(User.is_account_linked.is_(True)))
        ai_requests = await self.session.scalar(select(func.count(UsageLog.id)).where(UsageLog.action.like("ai%")))
        successful_payments = await self.session.scalar(select(func.count(Payment.id)).where(Payment.status == "paid"))
        stars_earned = await self.session.scalar(select(func.coalesce(func.sum(Payment.amount_stars), 0)).where(Payment.status == "paid"))
        promo_codes = await self.session.scalar(select(func.count(PromoCode.id)))
        referrals = await self.session.scalar(select(func.count(Referral.id)))
        bonus_given = await self.session.scalar(select(func.coalesce(func.sum(BonusTransaction.amount), 0)))
        return {
            "total_users": total_users or 0,
            "active_users": active_users or 0,
            "linked_accounts": linked_accounts or 0,
            "premium_users": premium_users or 0,
            "ai_requests": ai_requests or 0,
            "successful_payments": successful_payments or 0,
            "stars_earned": stars_earned or 0,
            "promo_codes": promo_codes or 0,
            "referrals": referrals or 0,
            "bonus_given": bonus_given or 0,
        }

    async def log_action(self, admin_id: int, action: str, target_user_id: int | None = None, details: str | None = None) -> None:
        self.session.add(AdminAction(admin_id=admin_id, action=action, target_user_id=target_user_id, details=details))
