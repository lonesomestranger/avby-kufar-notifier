from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.analyse_handler import URL_PATTERN, process_analysis_request
from app.bot.keyboards.inline import (
    get_ai_settings_keyboard,
    get_back_to_subscriptions_keyboard,
    get_main_menu_keyboard,
    get_subscriptions_keyboard,
)
from app.bot.keyboards.reply import get_menu_keyboard
from app.core.db_queries import (
    delete_subscription_by_id,
    get_or_create_user,
    get_subscription_by_id,
    get_user,
    get_user_subscriptions,
    toggle_ai_analysis,
)
from app.core.settings import settings
from app.services.filters_metadata import KUFAR_FILTERS
from app.services.unified_filters_metadata import UNIFIED_FILTERS

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    await get_or_create_user(
        session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await message.answer(
        "Привет! Я бот для отслеживания объявлений.",
        reply_markup=get_menu_keyboard(),
    )
    await handle_menu(message, state)


@router.message(F.text == "Меню")
@router.message(Command("menu"))
async def handle_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "my_subscriptions")
async def handle_my_subscriptions(callback: CallbackQuery, session: AsyncSession):
    subscriptions = await get_user_subscriptions(session, callback.from_user.id)
    await callback.message.edit_text(
        "Ваши подписки:", reply_markup=get_subscriptions_keyboard(subscriptions, page=0)
    )


@router.callback_query(F.data.startswith("my_subscriptions_page_"))
async def handle_subscriptions_pagination(
    callback: CallbackQuery, session: AsyncSession
):
    page = int(callback.data.split("_")[-1])
    subscriptions = await get_user_subscriptions(session, callback.from_user.id)
    markup = get_subscriptions_keyboard(subscriptions, page=page)
    await callback.message.edit_reply_markup(reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("view_sub_"))
async def handle_view_subscription(callback: CallbackQuery, session: AsyncSession):
    sub_id = int(callback.data.split("_")[2])
    sub = await get_subscription_by_id(session, sub_id, callback.from_user.id)

    if not sub:
        await callback.answer("Подписка не найдена.", show_alert=True)
        return

    params = sub.search.search_params
    platform = sub.search.platform
    platform_map = {"av": "AV.BY", "kufar": "KUFAR.BY"}

    details = [
        f"<b>Детали подписки #{sub.id}</b>\n",
        f"<b>Платформа:</b> {platform_map.get(platform)}",
        f"<b>Марка:</b> {params.get('brand_name', 'Любая')}",
        f"<b>Модель:</b> {params.get('model_name', 'Любая')}",
    ]

    price_value = params.get("price_usd[max]")
    price_text = f"${price_value}" if price_value is not None else "Любая"
    details.append(f"<b>Цена до:</b> {price_text}")

    has_filters = False
    if platform == "kufar" and "filters" in params and params["filters"]:
        has_filters = True
        details.append("\n<b>Дополнительные фильтры:</b>")
        filters_data = params["filters"]
        filters_metadata = KUFAR_FILTERS

        for key, selected_ids in filters_data.items():
            if key in filters_metadata and selected_ids:
                filter_meta = filters_metadata[key]
                option_names = [
                    opt["name"]
                    for opt in filter_meta["options"]
                    if opt["id"] in selected_ids
                ]
                if option_names:
                    details.append(
                        f"  • <i>{filter_meta['name_ru']}:</i> {', '.join(option_names)}"
                    )

    elif platform == "av":
        has_filters = True
        details.append("\n<b>Дополнительные фильтры:</b>")
        filters_metadata = UNIFIED_FILTERS

        for key, meta in filters_metadata.items():
            platform_key = meta["av_key"]
            if platform_key in params and params[platform_key]:
                selected_ids = params[platform_key]
                if not isinstance(selected_ids, list):
                    selected_ids = [selected_ids]

                option_names = []
                for opt in meta["options"]:
                    platform_value = opt["platform_values"]["av"]
                    if (
                        isinstance(platform_value, list)
                        and any(item in selected_ids for item in platform_value)
                    ) or (
                        not isinstance(platform_value, list)
                        and platform_value in selected_ids
                    ):
                        option_names.append(opt["name"])

                if option_names:
                    details.append(
                        f"  • <i>{meta['name_ru']}:</i> {', '.join(option_names)}"
                    )

    if not has_filters:
        details.append("\n<i>Дополнительные фильтры не заданы.</i>")

    await callback.message.edit_text(
        "\n".join(details), reply_markup=get_back_to_subscriptions_keyboard()
    )


@router.callback_query(F.data.startswith("delete_sub_"))
async def handle_delete_subscription(callback: CallbackQuery, session: AsyncSession):
    sub_id = int(callback.data.split("_")[2])
    deleted = await delete_subscription_by_id(session, sub_id, callback.from_user.id)
    if deleted:
        await callback.answer("Подписка удалена!", show_alert=True)
        subscriptions = await get_user_subscriptions(session, callback.from_user.id)
        await callback.message.edit_text(
            "Ваши подписки:", reply_markup=get_subscriptions_keyboard(subscriptions)
        )
    else:
        await callback.answer("Не удалось удалить подписку.", show_alert=True)


@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:", reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "ai_settings")
async def handle_ai_settings(callback: CallbackQuery, session: AsyncSession):
    await get_or_create_user(
        session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    user = await get_user(session, callback.from_user.id)
    text = (
        "Здесь вы можете включить автоматический анализ каждого объявления, "
        "которое приходит по вашим подпискам. Бот будет отвечать на сообщение с "
        "объявлением, присылая краткую сводку об автомобиле от ИИ."
    )
    await callback.message.edit_text(
        text, reply_markup=get_ai_settings_keyboard(user.ai_analysis_enabled)
    )


@router.callback_query(F.data == "ai_toggle")
async def handle_ai_toggle(callback: CallbackQuery, session: AsyncSession):
    if not settings.gemini_api_key:
        await callback.answer(
            "Функция анализа недоступна: не настроен API-ключ.", show_alert=True
        )
        return

    await get_or_create_user(
        session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )

    new_status = await toggle_ai_analysis(session, callback.from_user.id)
    await callback.message.edit_reply_markup(
        reply_markup=get_ai_settings_keyboard(new_status)
    )
    await callback.answer(
        f"Авто-анализ {'включен' if new_status else 'выключен'}", show_alert=True
    )


@router.message(Command("analyse"))
async def handle_analyse_command(message: Message):
    if not settings.gemini_api_key:
        await message.reply(
            "Функция анализа недоступна: не настроен API-ключ администратором."
        )
        return

    match = URL_PATTERN.search(message.text)
    if not match:
        await message.reply(
            "Пожалуйста, укажите ссылку на объявление после команды. "
            "Пример: `/analyse https://cars.av.by/bmw/3-seriya/1000000`"
        )
        return

    url = match.group(0)
    await process_analysis_request(message, url)
