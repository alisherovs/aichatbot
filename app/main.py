import asyncio
import logging
from app.config import get_settings
from app.database.session import init_db
from app.handlers import setup_routers
from app.loader import create_bot_and_dispatcher
from app.services.telegram_account.client_manager import start_enabled_clients
from app.utils.logger import setup_logging


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN .env faylida ko‘rsatilmagan.")
    await init_db()
    bot, dp = create_bot_and_dispatcher()
    dp.include_router(setup_routers())
    await start_enabled_clients(bot)
    logging.getLogger(__name__).info("TeleMind AI Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
