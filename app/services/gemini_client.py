import asyncio
import logging

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmBlockThreshold, HarmCategory

from app.core.settings import settings
from app.utils.image_downloader import download_image_to_bytes


async def analyze_ad(ad_data: dict) -> str | None:
    if not settings.gemini_api_key:
        logging.warning("GEMINI_CLIENT: API key is not configured.")
        return None

    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        data = ad_data.get("data", {})
        title = data.get("title", "Без названия")
        price_usd = data.get("price_usd", 0)
        params = data.get("params", "Нет данных")
        description = data.get("description", "Нет описания")
        options = ", ".join(data.get("options", []))

        prompt = f"""
Ты — опытный автомеханик и эксперт по автомобилям из СНГ. Твоя задача — дать краткий, но емкий анализ автомобиля по объявлению с точки зрения "опытного перекупа" для потенциального покупателя (или перекупа). Используй свои знания о конкретной модели из объявления, ее типичных проблемах ("болячках"), а также информацию из объявления.

**Информация из объявления:**
- **Заголовок:** {title}
- **Цена:** ${price_usd}
- **Основные параметры:** {params}
- **Описание от продавца:** {description}
- **Комплектация:** {options}

**Твоя задача:**
1.  **Общий вердикт:** Начни с краткого вывода о модели в целом (например, "BMW F30 с дизельным мотором N47 — популярный, но требовательный к обслуживанию автомобиль").
2.  **Плюсы модели:** Перечисли 2-3 ключевых преимущества этой модели/модификации.
3.  **Типичные проблемы ("болячки"):** Укажи 2-4 самых известных слабых места именно для этой модели с указанным мотором/коробкой. Если точных данных нет, опиши общие проблемы поколения. Особое внимание удели двигателю и коробке передач.
4.  **Анализ объявления:** Проанализируй текст и фото (если оно есть). Есть ли в описании продавца что-то подозрительное или, наоборот, позитивное (например, упоминание замены цепи ГРМ, обслуживания АКПП)? Отметь это.
5.  **На что обратить внимание при осмотре:** Дай 3-4 конкретных совета, что нужно проверить при встрече с продавцом, основываясь на "болячках" модели.
6.  **Итог:** Сделай краткий вывод, стоит ли рассматривать этот вариант к покупке и какие вопросы задать продавцу по телефону.

Ответ должен быть структурированным, без воды и без какого-либо форматирования (никаких Markdown или HTML тегов). Используй простые переносы строк для разделения пунктов.
"""

        image_urls = data.get("images", [])[:4]
        image_parts = []
        if image_urls:
            tasks = [download_image_to_bytes(url) for url in image_urls]
            image_bytes_list = await asyncio.gather(*tasks)
            for image_bytes in image_bytes_list:
                if image_bytes:
                    image_parts.append({"mime_type": "image/jpeg", "data": image_bytes})

        prompt_parts = [prompt, *image_parts]

        generation_config = GenerationConfig(
            temperature=0.1,
        )

        response = await model.generate_content_async(
            prompt_parts,
            generation_config=generation_config,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )

        if response.parts:
            return "".join(part.text for part in response.parts)
        else:
            logging.warning(
                f"GEMINI_CLIENT: No parts in response for ad {ad_data.get('url')}. Finish reason: {response.prompt_feedback, response.candidates[0].finish_reason}"
            )
            return "Анализ не удался. Модель не смогла сформировать полный ответ из-за внутренних ограничений."
    except Exception as e:
        logging.error(
            f"GEMINI_CLIENT: Failed to analyze ad {ad_data.get('url')}. Error: {e}",
            exc_info=True,
        )
        return "Не удалось получить анализ от ИИ. Попробуйте позже."
