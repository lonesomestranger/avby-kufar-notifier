from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import KeyboardButton


def get_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Меню")]], resize_keyboard=True
    )
    return builder
