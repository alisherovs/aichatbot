from aiogram.fsm.state import State, StatesGroup


class AccountLinkStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_2fa_password = State()


class AutoreplyStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_draft_edit = State()


class GroupLinkStates(StatesGroup):
    waiting_for_schedule_text = State()
    waiting_for_schedule_interval = State()
