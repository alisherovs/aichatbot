from __future__ import annotations

from datetime import datetime
from app.utils.security import safe_html


def fmt_dt(value: datetime | None) -> str:
    if not value:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


def menu_header(title: str, subtitle: str | None = None) -> str:
    if subtitle:
        return f"<b>{safe_html(title)}</b>\n\n{safe_html(subtitle)}"
    return f"<b>{safe_html(title)}</b>"
