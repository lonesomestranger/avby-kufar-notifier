import asyncio
import logging
import sys
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bot.handlers import analyse_handler, common, new_search
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.utils.commands import set_bot_commands
from app.core.database import get_db_url
from app.core.models import Base
from app.core.settings import settings
from app.services.currency_converter import CurrencyConverter
from app.services.scheduler import setup_scheduler


async def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    bot_start_time = datetime.now(timezone.utc)

    await CurrencyConverter.get_usd_rate()

    engine = create_async_engine(get_db_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    dp.update.outer_middleware(DbSessionMiddleware(session_maker=session_maker))

    dp.include_router(common.router)
    dp.include_router(new_search.router)
    dp.include_router(analyse_handler.router)

    scheduler = await setup_scheduler(
        bot=bot, session_maker=session_maker, bot_start_time=bot_start_time
    )
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)

    await set_bot_commands(bot)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
