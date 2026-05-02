from app.config import get_settings


def is_admin(telegram_id: int) -> bool:
    return telegram_id in get_settings().admin_id_set
