import datetime

from sqlalchemy import delete, select, update
from sqlalchemy import func as sql_func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.models import Ad, SentAd, Subscription, UniqueSearch, User
from app.utils.hash import get_search_hash


async def get_or_create_user(
    session: AsyncSession, user_id: int, username: str | None, first_name: str | None
):
    stmt = insert(User).values(
        user_id=user_id, username=username, first_name=first_name
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id"])
    await session.execute(stmt)
    await session.commit()


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def toggle_ai_analysis(session: AsyncSession, user_id: int) -> bool:
    user = await get_user(session, user_id)
    if not user:
        return False
    user.ai_analysis_enabled = not user.ai_analysis_enabled
    await session.commit()
    return user.ai_analysis_enabled


async def create_subscription(
    session: AsyncSession, user_id: int, platform: str, params: dict
):
    search_hash = get_search_hash(platform, params)

    search_stmt = insert(UniqueSearch).values(
        search_hash=search_hash, platform=platform, search_params=params
    )
    await session.execute(search_stmt.on_conflict_do_nothing())

    sub_stmt = insert(Subscription).values(
        user_id=user_id, search_hash=search_hash, is_active=True
    )
    await session.execute(sub_stmt.on_conflict_do_nothing())
    await session.commit()


async def get_active_searches(session: AsyncSession):
    stmt = (
        select(UniqueSearch)
        .join(Subscription, UniqueSearch.search_hash == Subscription.search_hash)
        .where(Subscription.is_active)
        .group_by(UniqueSearch.search_hash)
        .having(sql_func.count(Subscription.id) > 0)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_search_last_checked(session: AsyncSession, search_hash: str):
    stmt = (
        update(UniqueSearch)
        .where(UniqueSearch.search_hash == search_hash)
        .values(last_checked_at=datetime.datetime.now(datetime.timezone.utc))
    )
    await session.execute(stmt)
    await session.commit()


async def get_subscriptions_by_search_hash(session: AsyncSession, search_hash: str):
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(Subscription.search_hash == search_hash, Subscription.is_active)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def add_new_ads(session: AsyncSession, ads: list[dict]):
    if not ads:
        return []

    existing_urls_stmt = select(Ad.url).where(Ad.url.in_([ad["url"] for ad in ads]))
    result = await session.execute(existing_urls_stmt)
    existing_urls = {row[0] for row in result}

    new_ads_to_insert = [ad for ad in ads if ad["url"] not in existing_urls]

    if not new_ads_to_insert:
        return []

    stmt = insert(Ad).values(new_ads_to_insert)
    await session.execute(stmt.on_conflict_do_nothing())
    await session.commit()
    return new_ads_to_insert


async def get_user_subscriptions(session: AsyncSession, user_id: int):
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.search))
        .where(Subscription.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_subscription_by_id(
    session: AsyncSession, subscription_id: int, user_id: int
):
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.search))
        .where(Subscription.id == subscription_id, Subscription.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_subscription_by_id(
    session: AsyncSession, subscription_id: int, user_id: int
):
    stmt = delete(Subscription).where(
        Subscription.id == subscription_id, Subscription.user_id == user_id
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def mark_ads_as_sent(
    session: AsyncSession, subscription_id: int, ad_urls: list[str]
):
    if not ad_urls:
        return
    sent_ads_data = [
        {"subscription_id": subscription_id, "ad_url": url} for url in ad_urls
    ]
    stmt = insert(SentAd).values(sent_ads_data)
    await session.execute(stmt.on_conflict_do_nothing())
    await session.commit()
