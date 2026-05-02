from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_ban_user = State()
    waiting_for_grant_user = State()
    waiting_for_bonus_user = State()
    waiting_for_bonus_amount = State()
    waiting_for_promo_credits = State()
    waiting_for_promo_plan = State()
