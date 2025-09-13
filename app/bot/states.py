from aiogram.fsm.state import State, StatesGroup


class SearchState(StatesGroup):
    platform = State()
    brand = State()
    model = State()
    price_to = State()
    specific_filters = State()
    specific_filter_selection = State()


class AnalyseState(StatesGroup):
    waiting_for_link = State()
