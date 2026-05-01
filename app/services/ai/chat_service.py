"""Backward-compatible chat service wrapper.

New code should import app.services.ai.ai_service directly.
"""

from app.services.ai.ai_service import AIServiceError as ChatAIServiceError
from app.services.ai.ai_service import generate_chat_response


def normalize_chat_provider(provider: str | None) -> str:
    return "groq"


def chat_provider_title(provider: str | None = None) -> str:
    return "AI"
