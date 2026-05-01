from aiogram.fsm.state import State, StatesGroup


class ToolStates(StatesGroup):
    waiting_for_input = State()
