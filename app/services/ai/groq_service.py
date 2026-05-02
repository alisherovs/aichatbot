from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from app.config import get_settings
from app.services.ai.response_validator import build_repair_prompt, validate_ai_response
from app.services.prompt_service import add_strict_ai_instructions, build_autoreply_messages, build_tool_messages

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
TEMPORARY_STATUS_CODES = {500, 502, 503, 504}
FALLBACK_TEXT = "Kechirasiz, javobni aniq shakllantirishda muammo bo‘ldi. Savolni biroz boshqacharoq yozib yuboring."


class GroqServiceError(Exception):
    pass


class TemporaryGroqError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _expected_language(user_message: str) -> str | None:
    lowered = (user_message or "").lower()
    uz_hints = ("nima", "qanday", "nega", "uchun", "bilan", "kerak", "qil", "o‘", "g‘", "bo'l", "bo‘l")
    en_hints = ("what", "why", "how", "when", "where", "please", "explain", "write")
    if any(hint in lowered for hint in en_hints) and not any(hint in lowered for hint in uz_hints):
        return None
    return "uz"


def _last_user_message(messages: list[dict[str, str]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user" and item.get("content"):
            return str(item["content"])
    return ""


def _to_groq_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in add_strict_ai_instructions(messages):
        role = item.get("role") or "user"
        content = item.get("content") or ""
        if role not in {"system", "user", "assistant"}:
            role = "user"
        if content:
            result.append({"role": role, "content": str(content)})
    return result


def _extract_groq_text(data: dict[str, Any]) -> str:
    if not isinstance(data, dict):
        raise GroqServiceError("AI xizmati noto‘g‘ri formatda javob qaytardi.")
    if data.get("error"):
        message = (data.get("error") or {}).get("message") or "Noma’lum xato"
        raise GroqServiceError(_friendly_error(message=message))
    choices = data.get("choices") or []
    if not choices:
        raise TemporaryGroqError("empty_response")
    message = (choices[0] or {}).get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        raise TemporaryGroqError("empty_response")
    return text


def _friendly_error(status_code: int | None = None, message: str = "") -> str:
    lowered = (message or "").lower()
    if status_code == 401:
        return "AI kaliti noto‘g‘ri. Iltimos, GROQ_API_KEY qiymatini tekshiring."
    if status_code == 403:
        return "AI xizmatidan foydalanishga ruxsat yo‘q. Iltimos, API sozlamalarini tekshiring."
    if status_code == 404:
        return "Tanlangan AI modeli topilmadi. Iltimos, GROQ_MODEL qiymatini tekshiring."
    if status_code == 429 or "rate limit" in lowered:
        return "AI xizmati hozir limitga tushdi. Birozdan keyin qayta urinib ko‘ring."
    if status_code in TEMPORARY_STATUS_CODES:
        return "AI xizmati vaqtincha javob bermadi. Birozdan keyin qayta urinib ko‘ring."
    if status_code == 400:
        return "AI so‘rovi noto‘g‘ri shakllandi. Iltimos, savolni boshqacharoq yozing."
    return "AI xizmati hozir javob bera olmadi. Birozdan keyin qayta urinib ko‘ring."


async def _post_groq(messages: list[dict[str, str]], temperature: float | None = None, timeout: float | None = None) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        raise GroqServiceError("Hozir AI xizmati sozlanmagan. Iltimos, keyinroq urinib ko‘ring.")

    payload = {
        "model": settings.groq_model,
        "messages": _to_groq_messages(messages),
        "temperature": settings.ai_temperature if temperature is None else temperature,
        "top_p": settings.ai_top_p,
        "max_tokens": settings.ai_max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    effective_timeout = timeout or float(settings.ai_timeout_seconds or 45)

    async with httpx.AsyncClient(base_url=GROQ_BASE_URL, timeout=effective_timeout, headers=headers) as client:
        try:
            response = await client.post("/chat/completions", json=payload)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise TemporaryGroqError(exc.__class__.__name__) from exc

    logger.info(
        "Groq response status=%s model=%s temperature=%s max_tokens=%s",
        response.status_code,
        settings.groq_model,
        payload["temperature"],
        settings.ai_max_tokens,
    )

    if response.status_code in TEMPORARY_STATUS_CODES:
        raise TemporaryGroqError("temporary_status", response.status_code)

    data: dict[str, Any]
    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Groq malformed JSON status=%s body_len=%s", response.status_code, len(response.text or ""))
        if response.status_code >= 500:
            raise TemporaryGroqError("malformed_response", response.status_code) from exc
        raise GroqServiceError(_friendly_error(response.status_code)) from exc

    if response.status_code >= 400:
        logger.warning("Groq non-retryable error status=%s model=%s", response.status_code, settings.groq_model)
        raise GroqServiceError(_friendly_error(response.status_code, str(data.get("error") or "")))

    return _extract_groq_text(data)


async def _call_with_retries(messages: list[dict[str, str]], temperature: float | None = None, timeout: float | None = None) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return await _post_groq(messages, temperature=temperature, timeout=timeout)
        except TemporaryGroqError as exc:
            last_error = exc
            if attempt >= 3:
                break
            delay = (1.2 * (2 ** (attempt - 1))) + random.uniform(0, 0.5 * attempt)
            logger.warning(
                "Groq temporary failure attempt=%s status=%s model=%s retry_after=%.2f",
                attempt,
                exc.status_code,
                get_settings().groq_model,
                delay,
            )
            await asyncio.sleep(delay)
    raise GroqServiceError("AI xizmati vaqtincha javob bermadi. Birozdan keyin qayta urinib ko‘ring.") from last_error


async def _generate_validated(messages: list[dict[str, str]], timeout: float | None = None) -> str:
    original_user_message = _last_user_message(messages)
    expected_language = _expected_language(original_user_message)
    text = await _call_with_retries(messages, timeout=timeout)
    ok, reason = validate_ai_response(text, original_user_message, expected_language=expected_language)
    logger.info("Groq validation result=%s reason=%s", ok, reason)
    if ok:
        return text

    repair_messages = list(messages)
    repair_messages.append(
        {
            "role": "user",
            "content": build_repair_prompt(original_user_message, text, reason),
        }
    )
    try:
        repaired = await _call_with_retries(repair_messages, temperature=0.1, timeout=timeout)
    except GroqServiceError:
        logger.warning("Groq repair failed reason=%s", reason)
        return FALLBACK_TEXT

    ok, repair_reason = validate_ai_response(repaired, original_user_message, expected_language=expected_language)
    logger.info("Groq repair validation result=%s reason=%s", ok, repair_reason)
    return repaired if ok else FALLBACK_TEXT


async def generate_text(user_message: str, system_prompt: str, context: list | None = None) -> str:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in context or []:
        if isinstance(item, dict) and item.get("role") and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_message})
    return await _generate_validated(messages)


async def generate_from_messages(messages: list[dict[str, str]], timeout: float | None = None) -> str:
    return await _generate_validated(messages, timeout=timeout)


async def generate_tool_response(tool_type: str, user_input: str, user) -> str:
    return await generate_from_messages(build_tool_messages(user, tool_type, user_input))


async def generate_autoreply(user, incoming_text: str, context: list | None = None) -> str:
    return await generate_from_messages(build_autoreply_messages(user, incoming_text, context=context), timeout=20)
