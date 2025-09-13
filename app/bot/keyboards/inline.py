from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.models import Subscription


def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚀 Новый поиск", callback_data="new_search"))
    builder.row(
        InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subscriptions")
    )
    builder.row(
        InlineKeyboardButton(
            text="🚀 Анализ по ссылке", callback_data="analyse_by_link"
        )
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки ИИ", callback_data="ai_settings")
    )
    return builder.as_markup()


def get_cancel_analysis_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main")
    )
    return builder.as_markup()


def get_ai_settings_keyboard(is_enabled: bool):
    builder = InlineKeyboardBuilder()
    status_text = "✅ Включен" if is_enabled else "❌ Выключен"
    builder.row(
        InlineKeyboardButton(
            text=f"Авто-анализ объявлений: {status_text}", callback_data="ai_toggle"
        )
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    return builder.as_markup()


def get_platform_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="AV.BY", callback_data="platform_av"),
        InlineKeyboardButton(text="KUFAR.BY", callback_data="platform_kufar"),
    )
    builder.row(InlineKeyboardButton(text="Оба сайта", callback_data="platform_both"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    return builder.as_markup()


def create_paginated_keyboard(
    items: list,
    page: int = 0,
    page_size: int = 18,
    action_prefix: str = "item_select",
    page_prefix: str = "item_page",
    add_any_button: bool = False,
    back_callback: str = "back_to_main",
):
    builder = InlineKeyboardBuilder()
    start_offset = page * page_size
    end_offset = start_offset + page_size

    for item in items[start_offset:end_offset]:
        builder.button(text=item["name"], callback_data=f"{action_prefix}_{item['id']}")

    builder.adjust(3)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="<<", callback_data=f"{page_prefix}_{page - 1}")
        )

    total_pages = (len(items) + page_size - 1) // page_size
    if total_pages > 1:
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
        )

    if end_offset < len(items):
        nav_buttons.append(
            InlineKeyboardButton(text=">>", callback_data=f"{page_prefix}_{page + 1}")
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    if add_any_button:
        builder.row(
            InlineKeyboardButton(text="➡️ Любая", callback_data=f"{action_prefix}_any")
        )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
    return builder.as_markup()


def get_text_input_keyboard(back_callback: str, skip: bool = True):
    builder = InlineKeyboardBuilder()
    if skip:
        builder.button(text="➡️ Пропустить", callback_data="skip_step")
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    return builder.as_markup()


def get_confirmation_keyboard(back_callback: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Сохранить и отслеживать", callback_data="confirm_search"
        )
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
    return builder.as_markup()


def get_specific_filters_keyboard(current_filters: dict, filters_metadata: dict):
    builder = InlineKeyboardBuilder()
    for key, meta in filters_metadata.items():
        is_selected = "✅" if current_filters.get(key) else "❌"
        builder.button(
            text=f"{meta['name_ru']} {is_selected}", callback_data=f"edit_filter_{key}"
        )

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text="✅ Завершить и сохранить", callback_data="finish_filters"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к цене", callback_data="back_to_price_from_filters"
        )
    )
    return builder.as_markup()


def get_filter_options_keyboard(options: list, selected_ids: list, filter_key: str):
    builder = InlineKeyboardBuilder()
    for option in options:
        is_selected = "✅" if option["id"] in selected_ids else " "
        builder.button(
            text=f"{is_selected} {option['name']}",
            callback_data=f"toggle_option_{option['id']}",
        )

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Сохранить и назад", callback_data="save_specific_filter"
        )
    )
    return builder.as_markup()


def format_params_for_display(platform: str, params: dict) -> str:
    brand = params.get("brand_name", "Любая")
    model = params.get("model_name", "Любая")
    price = params.get("price_usd[max]", "Любая")

    model_display = model if model != "Любая" else ""
    full_name = f"{brand} {model_display}".strip()

    if len(full_name) > 20:
        full_name = full_name[:19] + "..."

    return f"{platform.upper()}: {full_name}, до ${price}"


def get_subscriptions_keyboard(
    subscriptions: list[Subscription], page: int = 0, page_size: int = 5
):
    builder = InlineKeyboardBuilder()

    start_offset = page * page_size
    end_offset = start_offset + page_size

    for sub in subscriptions[start_offset:end_offset]:
        text = format_params_for_display(sub.search.platform, sub.search.search_params)
        builder.row(
            InlineKeyboardButton(text=text, callback_data=f"view_sub_{sub.id}"),
            InlineKeyboardButton(text="❌", callback_data=f"delete_sub_{sub.id}"),
        )

    nav_buttons = []
    total_pages = (len(subscriptions) + page_size - 1) // page_size

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="<<", callback_data=f"my_subscriptions_page_{page - 1}"
            )
        )
    if total_pages > 1:
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
        )
    if end_offset < len(subscriptions):
        nav_buttons.append(
            InlineKeyboardButton(
                text=">>", callback_data=f"my_subscriptions_page_{page + 1}"
            )
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main")
    )
    return builder.as_markup()


def get_back_to_subscriptions_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к подпискам", callback_data="my_subscriptions"
        )
    )
    return builder.as_markup()
