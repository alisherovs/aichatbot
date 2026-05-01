import html


def safe_html(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
