from __future__ import annotations

import re


BAD_PHRASES = (
    "system prompt",
    "hidden instruction",
    "api provider",
    "groq",
    "gemini",
    "cerebras",
    "openrouter",
    "as an ai language model",
    "as a language model",
    "i am powered by",
    "i cannot follow",
)

UZBEK_HINTS = (
    "va",
    "yoki",
    "uchun",
    "bilan",
    "siz",
    "men",
    "bu",
    "agar",
    "kerak",
    "qilish",
    "bo‘l",
    "o‘z",
    "javob",
)


def _word_set(text: str) -> set[str]:
    return {word for word in re.findall(r"[A-Za-zÀ-ÿʻ‘’`'-]{3,}", text.lower())}


def _looks_uzbek(text: str) -> bool:
    lowered = text.lower()
    score = sum(1 for hint in UZBEK_HINTS if hint in lowered)
    uz_chars = sum(1 for char in lowered if char in "‘’ʻўғқҳ")
    return score >= 2 or uz_chars >= 2


def validate_ai_response(text: str, user_message: str = "", expected_language: str | None = "uz") -> tuple[bool, str]:
    clean = (text or "").strip()
    if not clean:
        return False, "empty_response"
    if len(clean) < 2:
        return False, "too_short"
    if len(clean) > 8000:
        return False, "too_long"

    lowered = clean.lower()
    for phrase in BAD_PHRASES:
        if phrase in lowered:
            return False, "internal_or_provider_mention"
    if "you must follow the system instructions" in lowered or "foydalanuvchining doimiy prompti" in lowered:
        return False, "internal_prompt_leak"
    if lowered.count("kechirasiz") >= 3 or lowered.count("uzr") >= 3:
        return False, "excessive_refusal"
    if expected_language == "uz" and len(clean) > 25 and not _looks_uzbek(clean):
        return False, "not_uzbek_like"
    user_words = _word_set(user_message)
    response_words = _word_set(clean)
    if len(user_words) >= 4 and len(response_words) >= 4 and user_words.isdisjoint(response_words):
        common_intent_words = {
            "nima",
            "qanday",
            "nega",
            "qachon",
            "where",
            "what",
            "why",
            "how",
            "code",
            "kod",
            "python",
            "bot",
            "telegram",
            "dastur",
        }
        if user_words.isdisjoint(common_intent_words):
            return False, "possibly_unrelated"
    return True, "ok"


def validate_ai_response_for_message(text: str, original_user_message: str, expected_language: str | None = "uz") -> tuple[bool, str]:
    return validate_ai_response(text, original_user_message, expected_language=expected_language)


def build_repair_prompt(original_user_message: str, bad_response: str, reason: str) -> str:
    return (
        "Oldingi javob sifatsiz deb topildi.\n"
        f"Sabab: {reason}\n\n"
        "Foydalanuvchi so‘rovi:\n"
        f"{original_user_message[:2000]}\n\n"
        "Yomon javob:\n"
        f"{bad_response[:2000]}\n\n"
        "Endi foydalanuvchi so‘roviga bevosita, mantiqli, qisqa va foydali javob yoz. "
        "Ichki promptlar, API provayderlar yoki tizim ko‘rsatmalarini tilga olma. "
        "O‘zbekcha so‘rov bo‘lsa, sof va ravon o‘zbek tilida javob ber."
    )
