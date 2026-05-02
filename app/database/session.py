from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    import app.database.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            async def add_column_if_missing(table: str, column: str, ddl: str) -> None:
                rows = await conn.execute(text(f"PRAGMA table_info({table})"))
                existing_cols = {row[1] for row in rows.fetchall()}
                if column not in existing_cols:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

            columns = await conn.execute(text("PRAGMA table_info(users)"))
            existing = {row[1] for row in columns.fetchall()}
            if "selected_persona" not in existing:
                await conn.execute(text("ALTER TABLE users ADD COLUMN selected_persona VARCHAR(64) NOT NULL DEFAULT 'bilimdon'"))
            if "preferred_ai_provider" not in existing:
                await conn.execute(text("ALTER TABLE users ADD COLUMN preferred_ai_provider VARCHAR(32) NOT NULL DEFAULT 'groq'"))
            await add_column_if_missing("users", "premium_until", "DATETIME")
            await add_column_if_missing("users", "bonus_credits", "INTEGER NOT NULL DEFAULT 0")
            await add_column_if_missing("users", "legal_accepted_at", "DATETIME")
            if "limit_reset_date" not in existing:
                await conn.execute(text("ALTER TABLE users ADD COLUMN limit_reset_date DATE"))
                await conn.execute(text("UPDATE users SET limit_reset_date = date('now') WHERE limit_reset_date IS NULL"))
            await conn.execute(text("UPDATE users SET daily_limit = 30 WHERE plan = 'free' AND daily_limit != 30"))
            await conn.execute(text("UPDATE users SET daily_limit = 150 WHERE plan = 'pro' AND daily_limit != 150"))
            await conn.execute(text("UPDATE users SET daily_limit = 300 WHERE plan = 'business' AND daily_limit != 300"))
            await conn.execute(text("UPDATE users SET preferred_ai_provider = 'groq' WHERE preferred_ai_provider IS NULL OR preferred_ai_provider != 'groq'"))
            await conn.execute(text("UPDATE users SET selected_persona = 'bilimdon' WHERE selected_persona IS NULL OR selected_persona = '' OR selected_persona = 'yordamchi'"))
            await add_column_if_missing("ai_autoreply_settings", "persona", "VARCHAR(64) NOT NULL DEFAULT 'yordamchi'")
            await add_column_if_missing("ai_autoreply_settings", "reply_only_when_away", "BOOLEAN NOT NULL DEFAULT 0")
            await add_column_if_missing("ai_autoreply_settings", "away_after_minutes", "INTEGER NOT NULL DEFAULT 5")
            await add_column_if_missing("ai_autoreply_settings", "used_today", "INTEGER NOT NULL DEFAULT 0")
            await add_column_if_missing("ai_autoreply_settings", "reset_date", "DATE")
            await add_column_if_missing("ai_autoreply_settings", "notify_owner_on_reply", "BOOLEAN NOT NULL DEFAULT 0")
            await conn.execute(text("UPDATE ai_autoreply_settings SET reset_date = date('now') WHERE reset_date IS NULL"))
            await conn.execute(text("UPDATE ai_autoreply_settings SET mode = 'assistant_only' WHERE mode IN ('offline_only','schedule') OR mode IS NULL"))
            await add_column_if_missing("autoreply_logs", "peer_id", "BIGINT NOT NULL DEFAULT 0")
            await add_column_if_missing("autoreply_logs", "peer_name", "VARCHAR(255)")
            await add_column_if_missing("autoreply_logs", "skipped_reason", "VARCHAR(64)")
            await add_column_if_missing("autoreply_logs", "persona_key", "VARCHAR(64)")
            await add_column_if_missing("autoreply_logs", "provider", "VARCHAR(64)")
            await add_column_if_missing("autoreply_logs", "error_text", "TEXT")
            await conn.execute(text("UPDATE autoreply_logs SET peer_id = incoming_chat_id WHERE peer_id = 0"))
            await add_column_if_missing("payments", "telegram_id", "BIGINT")
            await add_column_if_missing("payments", "amount_stars", "INTEGER NOT NULL DEFAULT 0")
            await add_column_if_missing("payments", "invoice_payload", "VARCHAR(255)")
            await add_column_if_missing("payments", "telegram_payment_charge_id", "VARCHAR(255)")
            await add_column_if_missing("payments", "provider_payment_charge_id", "VARCHAR(255)")
            await add_column_if_missing("payments", "paid_at", "DATETIME")
