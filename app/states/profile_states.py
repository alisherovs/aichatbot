from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    waiting_for_link_code = State()
