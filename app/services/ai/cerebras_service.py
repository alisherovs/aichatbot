from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from app.config import get_settings
from app.services.ai.response_validator import build_repair_prompt, validate_ai_response_for_message
from app.services.prompt_service import add_cerebras_strict_instructions

logger = logging.getLogger(__name__)


class CerebrasServiceError(Exception):
    pass


class TemporaryCerebrasError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


TEMPORARY_STATUS_CODES = {500, 502, 503, 504}
RETRY_DELAYS = (1.0, 2.0)
FALLBACK_TEXT = "Kechirasiz, javobni aniq shakllantirishda muammo bo‘ldi. Savolni biroz boshqacharoq yozib yuboring."


def _status_code_from_exception(exc: Exception) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _is_temporary_exception(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    status_code = _status_code_from_exception(exc)
    return status_code in TEMPORARY_STATUS_CODES


def _to_cerebras_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in add_cerebras_strict_instructions(messages):
        role = item.get("role") or "user"
        content = item.get("content") or ""
        if role not in {"system", "user", "assistant"}:
            role = "user"
        result.append({"role": role, "content": content})
    return result


def _last_user_message(messages: list[dict[str, str]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user" and item.get("content"):
            return str(item["content"])
    return ""


def _expected_language(user_message: str) -> str | None:
    lowered = user_message.lower()
    uz_hints = ("nima", "qanday", "nega", "uchun", "bilan", "kerak", "qil", "o‘", "g‘", "sh")
    en_hints = ("what", "why", "how", "when", "where", "please", "explain", "write")
    if any(hint in lowered for hint in en_hints) and not any(hint in lowered for hint in uz_hints):
        return None
    return "uz"


def _extract_cerebras_text(completion: Any) -> str:
    try:
        text = completion.choices[0].message.content
    except Exception as exc:
        raise TemporaryCerebrasError("empty_response") from exc
    text = (text or "").strip()
    if not text:
        raise TemporaryCerebrasError("empty_response")
    return text


def _create_completion_sync(messages: list[dict[str, str]], temperature: float | None = None) -> str:
    settings = get_settings()
    if not settings.cerebras_api_key:
        raise CerebrasServiceError("Cerebras API kaliti sozlanmagan.")
    try:
        from cerebras.cloud.sdk import Cerebras
    except ImportError as exc:
        raise CerebrasServiceError("Cerebras SDK o‘rnatilmagan. requirements.txt orqali paketlarni qayta o‘rnating.") from exc

    client = Cerebras(api_key=settings.cerebras_api_key)
    request = {
        "messages": _to_cerebras_messages(messages),
        "model": settings.cerebras_model,
        "max_tokens": settings.ai_max_tokens,
        "temperature": settings.ai_temperature if temperature is None else temperature,
        "top_p": settings.ai_top_p,
        "stream": False,
    }
    logger.info(
        "Cerebras request model=%s temperature=%s max_tokens=%s",
        settings.cerebras_model,
        request["temperature"],
        settings.ai_max_tokens,
    )
    try:
        completion = client.chat.completions.create(**request)
    except TypeError:
        legacy_request = dict(request)
        legacy_request["max_completion_tokens"] = legacy_request.pop("max_tokens")
        try:
            completion = client.chat.completions.create(**legacy_request)
        except Exception as exc:
            status_code = _status_code_from_exception(exc)
            logger.warning("Cerebras legacy request failed model=%s status=%s error=%s", settings.cerebras_model, status_code, exc.__class__.__name__)
            if _is_temporary_exception(exc):
                raise TemporaryCerebrasError("temporary_request_failure", status_code) from exc
            raise CerebrasServiceError("Cerebras hozir javob bera olmadi. Iltimos, birozdan keyin qayta urinib ko‘ring.") from exc
    except Exception as exc:
        status_code = _status_code_from_exception(exc)
        logger.warning("Cerebras request failed model=%s status=%s error=%s", settings.cerebras_model, status_code, exc.__class__.__name__)
        if _is_temporary_exception(exc):
            raise TemporaryCerebrasError("temporary_request_failure", status_code) from exc
        raise CerebrasServiceError("Cerebras hozir javob bera olmadi. Iltimos, birozdan keyin qayta urinib ko‘ring.") from exc
    return _extract_cerebras_text(completion)


async def _call_once(messages: list[dict[str, str]], temperature: float | None = None, timeout: float | None = None) -> str:
    settings = get_settings()
    effective_timeout = timeout or float(settings.ai_timeout_seconds or 45)
    return await asyncio.wait_for(
        asyncio.to_thread(_create_completion_sync, messages, temperature),
        timeout=effective_timeout,
    )


async def _call_with_temporary_retries(messages: list[dict[str, str]], temperature: float | None = None) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return await _call_once(messages, temperature=temperature)
        except asyncio.TimeoutError as exc:
            last_error = exc
            reason = "timeout"
            status_code = None
        except TemporaryCerebrasError as exc:
            last_error = exc
            reason = str(exc)
            status_code = exc.status_code
        if attempt >= 3:
            break
        delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)] + random.uniform(0, 0.4)
        logger.warning(
            "Cerebras retry reason=%s attempt=%s status=%s retry_after=%.2f",
            reason,
            attempt,
            status_code,
            delay,
        )
        await asyncio.sleep(delay)
    raise CerebrasServiceError("Cerebras hozir vaqtincha band. Iltimos, birozdan keyin qayta urinib ko‘ring.") from last_error


async def generate_cerebras_text(messages: list[dict[str, str]]) -> str:
    original_user_message = _last_user_message(messages)
    expected_language = _expected_language(original_user_message)
    try:
        text = await _call_with_temporary_retries(messages)
    except CerebrasServiceError:
        raise

    ok, reason = validate_ai_response_for_message(text, original_user_message, expected_language=expected_language)
    logger.info("Cerebras validation result=%s reason=%s", ok, reason)
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
        repaired = await _call_with_temporary_retries(repair_messages, temperature=0.1)
    except CerebrasServiceError:
        logger.warning("Cerebras repair failed reason=%s", reason)
        return FALLBACK_TEXT

    ok, repair_reason = validate_ai_response_for_message(repaired, original_user_message, expected_language=expected_language)
    logger.info("Cerebras repair validation result=%s reason=%s", ok, repair_reason)
    if ok:
        return repaired
    return FALLBACK_TEXT
