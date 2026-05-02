from aiogram import Router
from app.handlers import account, admin, ai_chat, autoreply, common, payments, personas, premium, profile, prompt, rewards, start, tools


def setup_routers() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(ai_chat.router)
    router.include_router(tools.router)
    router.include_router(personas.router)
    router.include_router(prompt.router)
    router.include_router(rewards.router)
    router.include_router(account.router)
    router.include_router(autoreply.router)
    router.include_router(profile.router)
    router.include_router(premium.router)
    router.include_router(payments.router)
    router.include_router(admin.router)
    router.include_router(common.router)
    return router
