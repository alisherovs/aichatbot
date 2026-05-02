from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    ai_provider: str = Field(default="groq", alias="AI_PROVIDER")
    ai_temperature: float = Field(default=0.2, alias="AI_TEMPERATURE")
    ai_top_p: float = Field(default=0.8, alias="AI_TOP_P")
    ai_max_tokens: int = Field(default=700, alias="AI_MAX_TOKENS")
    telegram_api_id: str = Field(default="", alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(default="", alias="TELEGRAM_API_HASH")
    session_encryption_key: str = Field(default="", alias="SESSION_ENCRYPTION_KEY")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")
    database_url: str = Field(default="sqlite+aiosqlite:///bot.db", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    ai_timeout_seconds: int = Field(default=45, alias="AI_TIMEOUT_SECONDS")
    autoreply_debug: bool = Field(default=False, alias="AUTOREPLY_DEBUG")
    throttle_rate_seconds: float = Field(default=0.8, alias="THROTTLE_RATE_SECONDS")
    required_subscriptions: str = Field(default="", alias="REQUIRED_SUBSCRIPTIONS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def admin_id_set(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.admin_ids.split(","):
            raw = raw.strip()
            if raw.isdigit():
                ids.add(int(raw))
        return ids

    @property
    def telegram_api_id_int(self) -> int:
        return int(self.telegram_api_id) if str(self.telegram_api_id).strip().isdigit() else 0

    @property
    def required_subscription_items(self) -> list[str]:
        items: list[str] = []
        for chunk in self.required_subscriptions.replace("\n", ",").split(","):
            value = chunk.strip()
            if value:
                items.append(value)
        return items


@lru_cache
def get_settings() -> Settings:
    return Settings()
