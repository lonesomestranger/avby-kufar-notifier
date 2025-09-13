import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import get_cancel_analysis_keyboard
from app.bot.states import AnalyseState
from app.bot.utils.message_splitter import send_long_message
from app.core.settings import settings
from app.services.av_client import AvClient
from app.services.gemini_client import analyze_ad
from app.services.kufar_client import KufarClient

router = Router()
URL_PATTERN = re.compile(r"https?://\S+")


async def process_analysis_request(message: Message, url: str):
    ad_data = None
    thinking_message = await message.answer("Анализирую объявление... 🧠")

    try:
        if "av.by" in url:
            client = AvClient()
            ad_data = await client.get_ad_details(url)
        elif "kufar.by" in url:
            client = KufarClient()
            ad_data = await client.get_ad_details_by_url(url)
        else:
            await thinking_message.edit_text(
                "Поддерживаются только ссылки с av.by и kufar.by."
            )
            return

        if not ad_data:
            await thinking_message.edit_text(
                "Не удалось получить данные об объявлении."
            )
            return

        analysis_result = await analyze_ad(ad_data)

        await thinking_message.delete()

        if analysis_result:
            await send_long_message(message.bot, message.chat.id, analysis_result)
        else:
            await message.answer("Не удалось проанализировать объявление.")

    except Exception as e:
        logging.error(
            f"An unexpected error occurred in process_analysis_request for url {url}: {e}",
            exc_info=True,
        )
        try:
            await thinking_message.edit_text("Произошла ошибка при анализе объявления.")
        except Exception:
            await message.answer("Произошла ошибка при анализе объявления.")


@router.callback_query(F.data == "analyse_by_link")
async def start_analysis_by_link(callback: CallbackQuery, state: FSMContext):
    if not settings.gemini_api_key:
        await callback.answer(
            "Функция анализа недоступна: не настроен API-ключ.", show_alert=True
        )
        return

    await state.set_state(AnalyseState.waiting_for_link)
    sent_message = await callback.message.edit_text(
        "Отправьте ссылку на объявление (av.by или kufar.by) для анализа.",
        reply_markup=get_cancel_analysis_keyboard(),
    )
    await state.update_data(prompt_message_id=sent_message.message_id)
    await callback.answer()


@router.message(AnalyseState.waiting_for_link, F.text)
async def process_link_for_analysis(message: Message, state: FSMContext):
    match = URL_PATTERN.search(message.text)
    if not match:
        await message.reply("Пожалуйста, отправьте корректную ссылку.")
        return

    url = match.group(0)
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    await message.delete()
    if prompt_message_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id, message_id=prompt_message_id
            )
        except Exception:
            pass

    await state.clear()
    await process_analysis_request(message, url)
