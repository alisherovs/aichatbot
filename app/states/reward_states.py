from aiogram.fsm.state import State, StatesGroup


class RewardStates(StatesGroup):
    waiting_for_promo_code = State()
