from __future__ import annotations

import logging

from app.database.models import User
from app.services.ai.groq_service import GroqServiceError, generate_autoreply, generate_from_messages, generate_tool_response as groq_tool_response
from app.services.prompt_service import build_normal_messages

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    pass


async def generate_chat_response(user: User, message: str, context: list | None = None) -> str:
    messages = build_normal_messages(user, message, context=context)
    try:
        logger.debug("AI request user_id=%s mode=chat provider=groq persona=%s", user.id, user.selected_persona)
        return await generate_from_messages(messages)
    except GroqServiceError as exc:
        raise AIServiceError(str(exc)) from exc


async def generate_tool_response(user: User, tool_type: str, input_text: str) -> str:
    try:
        logger.debug("AI request user_id=%s mode=tool provider=groq tool=%s persona=%s", user.id, tool_type, user.selected_persona)
        return await groq_tool_response(tool_type, input_text, user)
    except GroqServiceError as exc:
        raise AIServiceError(str(exc)) from exc


async def generate_autoreply_response(user: User, incoming_text: str, context: list | None = None) -> str:
    try:
        logger.debug("AI request user_id=%s mode=autoreply provider=groq persona=%s", user.id, user.selected_persona)
        return await generate_autoreply(user, incoming_text, context=context)
    except GroqServiceError as exc:
        raise AIServiceError(str(exc)) from exc
