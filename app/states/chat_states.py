from aiogram.fsm.state import State, StatesGroup


class AIChatStates(StatesGroup):
    chatting = State()
