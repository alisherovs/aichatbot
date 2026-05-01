from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class OpenRouterServiceError(Exception):
    pass


class TemporaryOpenRouterError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


TEMPORARY_STATUS_CODES = {500, 502, 503, 504}
RETRY_DELAYS = (1.0, 2.0, 4.0)


def _sanitize(data: Any, api_key: str) -> Any:
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            lowered = str(key).lower()
            if "key" in lowered or "token" in lowered or "authorization" in lowered:
                result[key] = "***"
            else:
                result[key] = _sanitize(value, api_key)
        return result
    if isinstance(data, list):
        return [_sanitize(item, api_key) for item in data[:5]]
    if isinstance(data, str):
        text = data.replace(api_key, "***") if api_key else data
        return text[:1000] + "...<kesildi>" if len(text) > 1000 else text
    return data


def extract_openrouter_text(data: dict) -> str:
    if not isinstance(data, dict):
        raise OpenRouterServiceError("OpenRouter noto‘g‘ri formatda javob qaytardi.")
    if data.get("error"):
        error = data.get("error") or {}
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise OpenRouterServiceError(f"OpenRouter xatosi: {message or 'Noma’lum xato'}")
    choices = data.get("choices") or []
    if not choices:
        raise OpenRouterServiceError("OpenRouter javob qaytarmadi. Iltimos, savolni boshqacharoq yozib ko‘ring.")
    texts: list[str] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            texts.append(content.strip())
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    texts.append(str(part["text"]).strip())
    text = "\n".join(item for item in texts if item).strip()
    if not text:
        raise OpenRouterServiceError("OpenRouter matnli javob qaytarmadi.")
    return text


def _to_openrouter_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in messages:
        role = item.get("role") or "user"
        content = item.get("content") or ""
        if role == "assistant":
            mapped_role = "assistant"
        elif role == "system":
            mapped_role = "system"
        else:
            mapped_role = "user"
        result.append({"role": mapped_role, "content": content})
    return result


async def _post_openrouter(messages: list[dict[str, str]], timeout: float) -> str:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise OpenRouterServiceError("OpenRouter API kaliti sozlanmagan.")

    url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telemind.local",
        "X-Title": "TeleMind AI Bot",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": _to_openrouter_messages(messages),
        "temperature": 0.7,
    }
    request_timeout = httpx.Timeout(timeout, connect=10.0)
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
    logger.info("OpenRouter response status=%s model=%s", response.status_code, settings.openrouter_model)

    try:
        data = response.json()
    except Exception as exc:
        logger.warning("OpenRouter JSON parse failed status=%s body=%s", response.status_code, _sanitize(response.text, settings.openrouter_api_key))
        if response.status_code in TEMPORARY_STATUS_CODES:
            raise TemporaryOpenRouterError("OpenRouter vaqtincha noto‘g‘ri javob qaytardi.", response.status_code) from exc
        raise OpenRouterServiceError("OpenRouter noto‘g‘ri javob qaytardi.") from exc

    logger.debug("OpenRouter sanitized response=%s", _sanitize(data, settings.openrouter_api_key))
    if response.status_code in TEMPORARY_STATUS_CODES:
        message = ((data.get("error") or {}).get("message")) if isinstance(data, dict) else None
        raise TemporaryOpenRouterError(message or "OpenRouter vaqtincha javob bermadi.", response.status_code)
    if response.status_code >= 400:
        return extract_openrouter_text(data)
    return extract_openrouter_text(data)


async def generate_openrouter_text(messages: list[dict[str, str]], timeout: float | None = None) -> str:
    settings = get_settings()
    effective_timeout = timeout or float(settings.ai_timeout_seconds or 45)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return await _post_openrouter(messages, effective_timeout)
        except OpenRouterServiceError:
            raise
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, TemporaryOpenRouterError) as exc:
            last_error = exc
            if attempt >= 3:
                break
            delay = RETRY_DELAYS[attempt - 1] + random.uniform(0, 0.5)
            logger.warning(
                "OpenRouter temporary failure attempt=%s status=%s model=%s retry_after=%.2f",
                attempt,
                getattr(exc, "status_code", None),
                settings.openrouter_model,
                delay,
            )
            await asyncio.sleep(delay)
    raise OpenRouterServiceError("OpenRouter hozir vaqtincha band. Iltimos, birozdan keyin qayta urinib ko‘ring.") from last_error
