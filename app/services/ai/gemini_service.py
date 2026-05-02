from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from app.config import get_settings
from app.database.models import User
from app.services.prompt_service import build_autoreply_messages, build_normal_messages, build_tool_messages

logger = logging.getLogger(__name__)


class GeminiServiceError(Exception):
    pass


class TemporaryGeminiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


NON_RETRY_FINISH_REASONS = {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "OTHER"}
ALLOWED_FINISH_REASONS = {None, "STOP", "MAX_TOKENS"}
TEMPORARY_STATUS_CODES = {500, 502, 503, 504}
RETRY_DELAYS = (1.5, 3.0, 6.0)
RETRY_JITTERS = (0.5, 1.0, 2.0)


def _sanitize_gemini_response(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            lowered = str(key).lower()
            if "key" in lowered or "token" in lowered or "credential" in lowered:
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_gemini_response(value)
        return sanitized
    if isinstance(data, list):
        return [_sanitize_gemini_response(item) for item in data[:5]]
    if isinstance(data, str) and len(data) > 1000:
        return data[:1000] + "...<kesildi>"
    return data


def _sanitize_log_text(text: str, api_key: str) -> str:
    if not text:
        return ""
    safe = text
    if api_key:
        safe = safe.replace(api_key, "***")
    return safe[:1000]


def extract_gemini_text(data: dict) -> str:
    if not isinstance(data, dict):
        raise GeminiServiceError("Gemini noto‘g‘ri formatda javob qaytardi.")

    if "error" in data:
        err = data.get("error", {})
        msg = err.get("message", "Noma’lum Gemini xatosi")
        raise GeminiServiceError(f"Gemini xatosi: {msg}")

    prompt_feedback = data.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason")
    if block_reason:
        raise GeminiServiceError(
            f"Gemini javobni xavfsizlik sababli blokladi: {block_reason}"
        )

    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiServiceError(
            "Gemini javob qaytarmadi. Iltimos, savolni boshqacharoq yozib ko‘ring."
        )

    candidate = candidates[0] or {}
    finish_reason = candidate.get("finishReason")

    if finish_reason not in ALLOWED_FINISH_REASONS:
        logger.warning("Gemini finishReason: %s", finish_reason)
    if finish_reason in NON_RETRY_FINISH_REASONS:
        raise GeminiServiceError(
            "Gemini bu so‘rovga javob bera olmadi. Iltimos, savolni boshqacharoq yozib ko‘ring."
        )

    content = candidate.get("content") or {}
    parts = content.get("parts") or []

    texts = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            texts.append(part["text"])

    text = "\n".join(texts).strip()
    if not text:
        raise GeminiServiceError("Gemini matnli javob qaytarmadi.")

    return text


def _retry_delay(attempt_index: int) -> float:
    base = RETRY_DELAYS[min(attempt_index, len(RETRY_DELAYS) - 1)]
    jitter = RETRY_JITTERS[min(attempt_index, len(RETRY_JITTERS) - 1)]
    return base + random.uniform(0, jitter)


async def _post_gemini_model(
    model: str,
    payload: dict[str, Any],
    api_key: str,
    timeout: float,
) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    request_timeout = httpx.Timeout(timeout, connect=10.0)
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        response = await client.post(url, params={"key": api_key}, json=payload)
    logger.info("Gemini response status=%s model=%s", response.status_code, model)

    try:
        data = response.json()
    except Exception as exc:
        logger.warning(
            "Gemini JSON parse failed status=%s model=%s body=%s",
            response.status_code,
            model,
            _sanitize_log_text(response.text, api_key),
        )
        if response.status_code in TEMPORARY_STATUS_CODES:
            raise TemporaryGeminiError("Gemini vaqtincha noto‘g‘ri javob qaytardi.", response.status_code) from exc
        raise GeminiServiceError("Gemini noto‘g‘ri javob qaytardi.") from exc

    logger.debug("Gemini sanitized response model=%s data=%s", model, _sanitize_gemini_response(data))
    if response.status_code in TEMPORARY_STATUS_CODES:
        message = "Gemini vaqtincha javob bermadi."
        if isinstance(data, dict):
            message = ((data.get("error") or {}).get("message")) or message
        raise TemporaryGeminiError(message, response.status_code)
    if response.status_code >= 400:
        return extract_gemini_text(data)
    return extract_gemini_text(data)


async def _call_model_with_retries(
    model: str,
    payload: dict[str, Any],
    api_key: str,
    timeout: float,
    max_attempts: int,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await _post_gemini_model(model, payload, api_key, timeout)
        except GeminiServiceError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            status_code = None
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            last_error = exc
            status_code = None
        except TemporaryGeminiError as exc:
            last_error = exc
            status_code = exc.status_code
        except httpx.HTTPError as exc:
            last_error = exc
            status_code = None
        if attempt >= max_attempts:
            break
        delay = _retry_delay(attempt - 1)
        logger.warning(
            "Gemini temporary failure attempt=%s status=%s model=%s retry_after=%.2f",
            attempt,
            status_code,
            model,
            delay,
        )
        await asyncio.sleep(delay)
    raise TemporaryGeminiError("Gemini temporary failure after retries", getattr(last_error, "status_code", None)) from last_error


async def _call_gemini(messages: list[dict[str, str]], timeout: float | None = None) -> str:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiServiceError("Hozir AI xizmati sozlanmagan. Iltimos, keyinroq urinib ko‘ring.")
    effective_timeout = timeout or float(settings.ai_timeout_seconds or 45)
    prompt = "\n\n".join(f"{item['role']}: {item['content']}" for item in messages)
    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }
    try:
        return await _call_model_with_retries(
            settings.gemini_model,
            payload,
            settings.gemini_api_key,
            effective_timeout,
            max_attempts=4,
        )
    except TemporaryGeminiError as exc:
        fallback_model = (settings.gemini_fallback_model or "").strip()
        if fallback_model and fallback_model != settings.gemini_model:
            logger.warning("Gemini main model failed temporarily; trying fallback model=%s status=%s", fallback_model, exc.status_code)
            try:
                return await _call_model_with_retries(
                    fallback_model,
                    payload,
                    settings.gemini_api_key,
                    effective_timeout,
                    max_attempts=1,
                )
            except TemporaryGeminiError:
                pass
        raise GeminiServiceError("Gemini hozir vaqtincha band. Iltimos, birozdan keyin qayta urinib ko‘ring.")


async def generate_text(user_message: str, system_prompt: list[dict[str, str]] | str, context: list | None = None) -> str:
    if isinstance(system_prompt, list):
        messages = system_prompt
    else:
        messages = [{"role": "system", "content": system_prompt}]
        for item in context or []:
            if isinstance(item, dict) and item.get("role") and item.get("content"):
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": user_message})
    return await _call_gemini(messages)


async def generate_tool_response(tool_type: str, user_input: str, user: User) -> str:
    return await _call_gemini(build_tool_messages(user, tool_type, user_input))


async def generate_autoreply(user: User, incoming_text: str, context: list | None = None) -> str:
    return await _call_gemini(build_autoreply_messages(user, incoming_text, context=context), timeout=12)
