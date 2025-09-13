import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputMediaPhoto, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from curl_cffi.requests import AsyncSession as AsyncRequestsSession
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.utils.message_splitter import send_long_message
from app.core.db_queries import (
    add_new_ads,
    get_active_searches,
    get_subscriptions_by_search_hash,
    mark_ads_as_sent,
    update_search_last_checked,
)
from app.core.settings import settings
from app.services.av_client import AvClient
from app.services.gemini_client import analyze_ad
from app.services.kufar_client import KufarClient
from app.utils.image_downloader import download_image_to_buffer


async def process_search(search, session: AsyncSession, bot_start_time: datetime):
    last_checked_from_db = search.last_checked_at
    last_checked_aware = None

    if last_checked_from_db:
        if last_checked_from_db.tzinfo is None:
            last_checked_aware = last_checked_from_db.replace(tzinfo=timezone.utc)
        else:
            last_checked_aware = last_checked_from_db

    cutoff_time = (
        max(last_checked_aware, bot_start_time)
        if last_checked_aware
        else bot_start_time
    )

    if search.platform == "av":
        client = AvClient()
        params = {
            k: v
            for k, v in search.search_params.items()
            if not k.endswith(("_name", "_slug"))
        }
        found_ads = await client.find_ads(params)

        truly_new_ads = [
            ad
            for ad in found_ads
            if ad.get("published_at") and ad["published_at"] > cutoff_time
        ]

        if not truly_new_ads:
            return []

        new_ads_in_db = await add_new_ads(session, truly_new_ads)
        return new_ads_in_db

    elif search.platform == "kufar":
        client = KufarClient()
        params = {
            k: v
            for k, v in search.search_params.items()
            if not k.endswith(("_name", "_id"))
        }
        found_ads_raw = await client.find_ads_raw(params)
        if not found_ads_raw:
            return []

        ads_to_process = []
        for ad in found_ads_raw:
            list_time_str = ad.get("list_time")
            if not list_time_str:
                continue

            published_at = datetime.fromisoformat(list_time_str.replace("Z", "+00:00"))

            if published_at > cutoff_time:
                ads_to_process.append(
                    {
                        "raw_data": ad,
                        "parsed_data": {
                            "url": ad.get("ad_link"),
                            "ad_id": str(ad.get("ad_id")),
                            "platform": "kufar",
                            "published_at": published_at,
                            "data": {},
                        },
                    }
                )

        if not ads_to_process:
            return []

        ads_to_check_in_db = [item["parsed_data"] for item in ads_to_process]
        newly_inserted_ads = await add_new_ads(session, ads_to_check_in_db)

        if not newly_inserted_ads:
            return []

        new_ads_urls = {ad["url"] for ad in newly_inserted_ads}
        new_ads_raw_to_detail = [
            item["raw_data"]
            for item in ads_to_process
            if item["parsed_data"]["url"] in new_ads_urls
        ]

        detailed_ads = []
        async with AsyncRequestsSession(impersonate="chrome110") as detail_session:
            for raw_ad in new_ads_raw_to_detail:
                full_ad_data = await client.get_ad_details(detail_session, raw_ad)
                if full_ad_data:
                    detailed_ads.append(full_ad_data)
        return detailed_ads

    return []


async def send_ad_to_user(bot: Bot, user_id: int, ad: dict) -> Message | None:
    data = ad["data"]
    price = f"≈ ${data.get('price_usd', 0)} / {data.get('price_byn', 0)} р."

    description_snippet = data.get("description") or ""
    if len(description_snippet) > 300:
        description_snippet = description_snippet[:300] + "..."

    published_at_str = (
        ad["published_at"]
        .astimezone(datetime.now().astimezone().tzinfo)
        .strftime("%H:%M, %d.%m")
    )

    title = data.get("title", "Без названия").replace("\n", " ").strip()
    platform_name = ad["platform"].upper()
    linked_title = f'<a href="{ad["url"]}">{title}</a>'

    caption_parts = [
        f"<b>{platform_name}: {linked_title}</b>\n",
        f"<b>Цена:</b> {price}",
        f"<b>Параметры:</b> {data.get('params', 'Нет данных')}",
        f"<b>Опубликовано:</b> {published_at_str}",
    ]

    if phone := data.get("phone"):
        caption_parts.append(f"<b>Телефон:</b> <code>{phone}</code>")

    if description_snippet:
        caption_parts.append(f"\n<i>{description_snippet}</i>")

    caption = "\n".join(caption_parts)

    image_urls = data.get("images", [])

    if not image_urls:
        return await bot.send_message(
            chat_id=user_id, text=caption, disable_web_page_preview=True
        )

    first_image_buffer = await download_image_to_buffer(image_urls[0])
    if not first_image_buffer:
        return await bot.send_message(
            chat_id=user_id, text=caption, disable_web_page_preview=True
        )

    if len(image_urls) == 1:
        return await bot.send_photo(
            chat_id=user_id,
            photo=first_image_buffer,
            caption=caption,
        )
    else:
        media_group = [InputMediaPhoto(media=first_image_buffer, caption=caption)]

        tasks = [download_image_to_buffer(url) for url in image_urls[1:10]]
        remaining_images = await asyncio.gather(*tasks)

        for img_buffer in remaining_images:
            if img_buffer:
                media_group.append(InputMediaPhoto(media=img_buffer))

        if len(media_group) == 1:
            return await bot.send_photo(
                chat_id=user_id,
                photo=first_image_buffer,
                caption=caption,
            )
        else:
            sent_messages = await bot.send_media_group(
                chat_id=user_id, media=media_group
            )
            return sent_messages[0] if sent_messages else None


async def send_notifications(
    bot: Bot, session: AsyncSession, search_hash: str, new_ads: list[dict]
):
    if not new_ads:
        return

    subscriptions = await get_subscriptions_by_search_hash(session, search_hash)

    for sub in subscriptions:
        sent_ad_urls = []
        for ad in new_ads:
            sent_message = None
            try:
                sent_message = await send_ad_to_user(bot, sub.user_id, ad)
                sent_ad_urls.append(ad["url"])
                await asyncio.sleep(1)
            except TelegramAPIError as e:
                if "message is not modified" in str(e):
                    logging.warning(
                        f"Ad {ad.get('url')} was already sent to {sub.user_id}. Marking as sent."
                    )
                    sent_ad_urls.append(ad["url"])
                else:
                    logging.error(
                        f"Failed to send ad {ad.get('url')} to {sub.user_id}: {e}"
                    )

                if "bot was blocked by the user" in str(e):
                    logging.warning(
                        f"User {sub.user_id} blocked the bot. Deactivating subscriptions might be needed."
                    )
                    break
                continue
            except Exception as e:
                logging.error(
                    f"An unexpected error occurred while sending ad {ad.get('url')} to {sub.user_id}: {e}"
                )

            if (
                sent_message
                and sub.user.ai_analysis_enabled
                and settings.gemini_api_key
            ):
                try:
                    await bot.send_chat_action(sub.user_id, ChatAction.TYPING)
                    full_ad_data = ad
                    if ad["platform"] == "av":
                        av_client = AvClient()
                        detailed_data = await av_client.get_ad_details(ad["url"])
                        if detailed_data:
                            full_ad_data = detailed_data

                    analysis = await analyze_ad(full_ad_data)
                    if analysis:
                        await send_long_message(
                            bot,
                            sub.user_id,
                            analysis,
                            reply_to_message_id=sent_message.message_id,
                        )
                        await asyncio.sleep(1)
                except Exception as e:
                    logging.error(
                        f"Failed to send AI analysis for ad {ad.get('url')} to {sub.user_id}: {e}"
                    )

        if sent_ad_urls:
            await mark_ads_as_sent(session, sub.id, sent_ad_urls)


async def check_for_updates(
    bot: Bot, session_maker: async_sessionmaker, bot_start_time: datetime
):
    logging.info("Scheduler job started: Checking for updates...")
    async with session_maker() as session:
        active_searches = await get_active_searches(session)

        for search in active_searches:
            try:
                new_ads = await process_search(search, session, bot_start_time)
                if new_ads:
                    await send_notifications(bot, session, search.search_hash, new_ads)
                await update_search_last_checked(session, search.search_hash)
            except Exception as e:
                logging.error(f"Error processing search {search.search_hash}: {e}")
            finally:
                await asyncio.sleep(2)

    logging.info("Scheduler job finished.")


async def setup_scheduler(
    bot: Bot, session_maker: async_sessionmaker, bot_start_time: datetime
):
    scheduler = AsyncIOScheduler(timezone="Europe/Minsk")
    scheduler.add_job(
        check_for_updates,
        "interval",
        seconds=settings.scheduler_interval_seconds,
        args=(bot, session_maker, bot_start_time),
    )
    return scheduler
