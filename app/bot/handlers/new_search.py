from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import (
    create_paginated_keyboard,
    get_filter_options_keyboard,
    get_main_menu_keyboard,
    get_platform_keyboard,
    get_specific_filters_keyboard,
    get_text_input_keyboard,
)
from app.bot.states import SearchState
from app.core.db_queries import create_subscription
from app.services.data_fetcher import get_brands, get_models_for_brand
from app.services.filters_metadata import KUFAR_FILTERS
from app.services.unified_filters_metadata import UNIFIED_FILTERS

router = Router()


def build_summary_text(data: dict):
    platform_map = {"av": "AV.BY", "kufar": "KUFAR.BY", "both": "Оба сайта"}
    text = "<b>Текущий выбор:</b>\n"
    text += f"Платформа: {platform_map.get(data.get('platform'), 'Не выбрана')}\n"
    if data.get("brand_name"):
        text += f"Марка: {data.get('brand_name')}\n"
    if data.get("model_name"):
        text += f"Модель: {data.get('model_name')}\n"
    if data.get("price_to") is not None:
        text += f"Цена до: ${data.get('price_to')}\n"
    return text


async def ask_for_brand(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.brand)
    data = await state.get_data()
    total_steps = 5
    brands = await get_brands(data["platform"])
    if not brands:
        await callback.message.edit_text(
            "Не удалось загрузить список марок. Попробуйте позже.",
            reply_markup=get_main_menu_keyboard(),
        )
        await state.clear()
        return
    await callback.message.edit_text(
        f"{build_summary_text(data)}\n<b>Шаг 2/{total_steps}:</b> Выберите марку автомобиля:",
        reply_markup=create_paginated_keyboard(
            items=brands,
            action_prefix="brand_select",
            page_prefix="brand_page",
            add_any_button=True,
            back_callback="back_to_platform",
        ),
    )


async def ask_for_model(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.model)
    data = await state.get_data()
    total_steps = 5
    brand_id = data.get("brand_id")
    brand_slug = data.get("brand_slug")

    if not brand_id:
        await state.update_data(model_id=None, model_name=None, model_slug=None)
        await ask_for_price(callback, state)
        return

    models = await get_models_for_brand(data["platform"], brand_id, brand_slug)
    if not models:
        await state.update_data(model_id=None, model_name=None, model_slug=None)
        await callback.answer(
            "Для этой марки не найдено моделей, пропускаем шаг.", show_alert=True
        )
        await ask_for_price(callback, state)
        return

    await callback.message.edit_text(
        f"{build_summary_text(data)}\n<b>Шаг 3/{total_steps}:</b> Выберите модель:",
        reply_markup=create_paginated_keyboard(
            items=models,
            action_prefix="model_select",
            page_prefix="model_page",
            add_any_button=True,
            back_callback="back_to_brand",
        ),
    )


async def ask_for_price(event: Message | CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.price_to)
    data = await state.get_data()
    total_steps = 5
    text = f"{build_summary_text(data)}\n<b>Шаг 4/{total_steps}:</b> Введите максимальную цену в USD:"
    markup = get_text_input_keyboard(back_callback="back_to_model", skip=True)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup)
        await state.update_data(last_bot_message_id=event.message.message_id)
    else:
        sent_message = await event.answer(text, reply_markup=markup)
        await state.update_data(last_bot_message_id=sent_message.message_id)


async def ask_for_specific_filters(event: Message | CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.specific_filters)
    data = await state.get_data()
    platform = data.get("platform")

    if platform == "kufar":
        filters_metadata = KUFAR_FILTERS
    else:
        filters_metadata = UNIFIED_FILTERS

    text = f"{build_summary_text(data)}\n<b>Шаг 5/5:</b> Настройте доп. фильтры или завершите."
    markup = get_specific_filters_keyboard(data.get("filters", {}), filters_metadata)

    message_to_edit = event if isinstance(event, Message) else event.message

    if isinstance(event, CallbackQuery):
        await message_to_edit.edit_text(text, reply_markup=markup)
    else:
        last_bot_message_id = data.get("last_bot_message_id")
        if last_bot_message_id:
            try:
                await event.bot.edit_message_text(
                    chat_id=event.chat.id,
                    message_id=last_bot_message_id,
                    text=text,
                    reply_markup=markup,
                )
            except Exception:
                await event.answer(text, reply_markup=markup)
        else:
            await event.answer(text, reply_markup=markup)


@router.callback_query(F.data == "new_search")
async def handle_new_search(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(SearchState.platform)
    await callback.message.edit_text(
        "<b>Шаг 1/5:</b> Выберите площадку для поиска:",
        reply_markup=get_platform_keyboard(),
    )


@router.callback_query(F.data == "back_to_platform", SearchState.brand)
async def handle_back_to_platform(callback: CallbackQuery, state: FSMContext):
    await handle_new_search(callback, state)


@router.callback_query(F.data.startswith("platform_"), SearchState.platform)
async def handle_platform_selection(callback: CallbackQuery, state: FSMContext):
    platform = callback.data.split("_")[1]
    await state.update_data(platform=platform)
    await ask_for_brand(callback, state)


@router.callback_query(F.data.startswith("brand_page_"), SearchState.brand)
async def handle_brand_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[2])
    data = await state.get_data()
    brands = await get_brands(data["platform"])
    await callback.message.edit_reply_markup(
        reply_markup=create_paginated_keyboard(
            items=brands,
            page=page,
            action_prefix="brand_select",
            page_prefix="brand_page",
            add_any_button=True,
            back_callback="back_to_platform",
        )
    )


@router.callback_query(F.data.startswith("brand_select_"), SearchState.brand)
async def handle_brand_selection(callback: CallbackQuery, state: FSMContext):
    selection = callback.data.split("_")[2]
    if selection == "any":
        await state.update_data(brand_id=None, brand_name=None, brand_slug=None)
    else:
        brand_id = int(selection)
        data = await state.get_data()
        brands = await get_brands(data["platform"])
        brand_info = next((b for b in brands if b["id"] == brand_id), None)
        if brand_info:
            await state.update_data(
                brand_id=brand_id,
                brand_name=brand_info["name"],
                brand_slug=brand_info.get("slug"),
            )

    await ask_for_model(callback, state)


@router.callback_query(F.data == "back_to_brand", SearchState.model)
async def handle_back_to_brand(callback: CallbackQuery, state: FSMContext):
    await ask_for_brand(callback, state)


@router.callback_query(F.data.startswith("model_page_"), SearchState.model)
async def handle_model_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[2])
    data = await state.get_data()
    models = await get_models_for_brand(
        data["platform"], data["brand_id"], data["brand_slug"]
    )
    await callback.message.edit_reply_markup(
        reply_markup=create_paginated_keyboard(
            items=models,
            page=page,
            action_prefix="model_select",
            page_prefix="model_page",
            add_any_button=True,
            back_callback="back_to_brand",
        )
    )


@router.callback_query(F.data.startswith("model_select_"), SearchState.model)
async def handle_model_selection(callback: CallbackQuery, state: FSMContext):
    selection = callback.data.split("_")[2]
    if selection == "any":
        await state.update_data(model_id=None, model_name=None, model_slug=None)
    else:
        model_id = int(selection)
        data = await state.get_data()
        models = await get_models_for_brand(
            data["platform"], data["brand_id"], data["brand_slug"]
        )
        model_info = next((m for m in models if m["id"] == model_id), None)
        if model_info:
            await state.update_data(
                model_id=model_id,
                model_name=model_info["name"],
                model_slug=model_info.get("slug"),
            )

    await ask_for_price(callback, state)


@router.callback_query(F.data == "back_to_model", SearchState.price_to)
async def handle_back_to_model(callback: CallbackQuery, state: FSMContext):
    await ask_for_model(callback, state)


@router.callback_query(F.data == "skip_step", SearchState.price_to)
async def handle_skip_price(callback: CallbackQuery, state: FSMContext):
    await state.update_data(price_to=None)
    await ask_for_specific_filters(callback, state)


@router.message(SearchState.price_to)
async def handle_price_input(message: Message, state: FSMContext):
    try:
        price_to = int(message.text.strip())
        if price_to <= 0:
            raise ValueError("Price must be positive")
    except (ValueError, TypeError):
        await message.answer(
            "Пожалуйста, введите целое положительное число для цены или пропустите шаг."
        )
        return

    await state.update_data(price_to=price_to)
    await message.delete()
    await ask_for_specific_filters(message, state)


@router.callback_query(
    F.data == "back_to_price_from_filters", SearchState.specific_filters
)
async def handle_back_to_price_from_filters(callback: CallbackQuery, state: FSMContext):
    await ask_for_price(callback, state)


@router.callback_query(F.data.startswith("edit_filter_"), SearchState.specific_filters)
async def handle_edit_specific_filter(callback: CallbackQuery, state: FSMContext):
    filter_key = callback.data.split("edit_filter_")[1]
    await state.update_data(current_filter_key=filter_key)
    await state.set_state(SearchState.specific_filter_selection)

    data = await state.get_data()
    platform = data.get("platform")

    if platform == "kufar":
        filters_metadata = KUFAR_FILTERS
    else:
        filters_metadata = UNIFIED_FILTERS

    filter_info = filters_metadata[filter_key]
    current_selections = data.get("filters", {}).get(filter_key, [])

    await callback.message.edit_text(
        f"Выберите опции для '{filter_info['name_ru']}':",
        reply_markup=get_filter_options_keyboard(
            options=filter_info["options"],
            selected_ids=current_selections,
            filter_key=filter_key,
        ),
    )


@router.callback_query(
    F.data.startswith("toggle_option_"), SearchState.specific_filter_selection
)
async def handle_toggle_filter_option(callback: CallbackQuery, state: FSMContext):
    option_id_str = callback.data.split("_")[2]
    data = await state.get_data()
    filter_key = data["current_filter_key"]
    platform = data.get("platform")

    if platform == "kufar":
        filters_metadata = KUFAR_FILTERS
        option_id = int(option_id_str)
    else:
        filters_metadata = UNIFIED_FILTERS
        option_id = option_id_str

    filters = data.get("filters", {})
    if filter_key not in filters:
        filters[filter_key] = []

    if option_id in filters[filter_key]:
        filters[filter_key].remove(option_id)
    else:
        filters[filter_key].append(option_id)

    await state.update_data(filters=filters)

    filter_info = filters_metadata[filter_key]

    await callback.message.edit_reply_markup(
        reply_markup=get_filter_options_keyboard(
            options=filter_info["options"],
            selected_ids=filters[filter_key],
            filter_key=filter_key,
        )
    )


@router.callback_query(
    F.data == "save_specific_filter", SearchState.specific_filter_selection
)
async def handle_save_specific_filter(callback: CallbackQuery, state: FSMContext):
    await ask_for_specific_filters(callback, state)


@router.callback_query(F.data == "finish_filters", SearchState.specific_filters)
async def handle_confirm_search(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    data = await state.get_data()
    platform = data.get("platform")

    base_params = {
        "brand_name": data.get("brand_name"),
        "model_name": data.get("model_name"),
    }
    unified_filters = data.get("filters", {})

    def translate_filters(platform_name: str, filters: dict) -> dict:
        translated = {}
        filters_metadata = UNIFIED_FILTERS
        for unified_key, selected_ids in filters.items():
            if not selected_ids or unified_key not in filters_metadata:
                continue

            meta = filters_metadata[unified_key]
            platform_key = meta[f"{platform_name}_key"]

            platform_values = []
            for option in meta["options"]:
                if option["id"] in selected_ids:
                    value = option["platform_values"].get(platform_name)
                    if isinstance(value, list):
                        platform_values.extend(value)
                    elif value is not None:
                        platform_values.append(value)

            if platform_values:
                translated[platform_key] = platform_values
        return translated

    if platform == "av":
        av_specific_filters = translate_filters("av", unified_filters)
        av_params = base_params.copy()
        av_params.update(
            {
                "brands[0][brand]": data.get("brand_id"),
                "brands[0][model]": data.get("model_id"),
                "price_usd[max]": data.get("price_to"),
            }
        )
        av_params.update(av_specific_filters)
        av_params = {k: v for k, v in av_params.items() if v is not None}
        await create_subscription(session, callback.from_user.id, "av", av_params)

    elif platform == "kufar":
        kufar_specific_filters = translate_filters("kufar", unified_filters)
        kufar_params = base_params.copy()
        kufar_params.update(
            {
                "brand_slug": data.get("brand_slug"),
                "model_slug": data.get("model_slug"),
                "price_usd[max]": data.get("price_to"),
                "filters": kufar_specific_filters,
            }
        )
        kufar_params = {k: v for k, v in kufar_params.items() if v is not None}
        await create_subscription(session, callback.from_user.id, "kufar", kufar_params)

    elif platform == "both":
        av_specific_filters = translate_filters("av", unified_filters)
        av_params = base_params.copy()
        av_params.update(
            {
                "brands[0][brand]": data.get("brand_id"),
                "brands[0][model]": data.get("model_id"),
                "price_usd[max]": data.get("price_to"),
            }
        )
        av_params.update(av_specific_filters)
        av_params = {k: v for k, v in av_params.items() if v is not None}
        await create_subscription(session, callback.from_user.id, "av", av_params)

        kufar_specific_filters = translate_filters("kufar", unified_filters)
        kufar_params = base_params.copy()
        kufar_params.update(
            {
                "brand_slug": data.get("brand_slug"),
                "model_slug": data.get("model_slug"),
                "price_usd[max]": data.get("price_to"),
                "filters": kufar_specific_filters,
            }
        )
        kufar_params = {k: v for k, v in kufar_params.items() if v is not None}
        await create_subscription(session, callback.from_user.id, "kufar", kufar_params)

    await state.clear()
    await callback.message.edit_text(
        "✅ Подписка успешно создана! Вы получите уведомление о новых объявлениях.",
        reply_markup=get_main_menu_keyboard(),
    )
