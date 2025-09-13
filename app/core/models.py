import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ai_analysis_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")


class UniqueSearch(Base):
    __tablename__ = "unique_searches"
    search_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(10))
    search_params: Mapped[dict] = mapped_column(JSON)
    last_checked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="search")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    search_hash: Mapped[str] = mapped_column(ForeignKey("unique_searches.search_hash"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user: Mapped["User"] = relationship(back_populates="subscriptions")
    search: Mapped["UniqueSearch"] = relationship(back_populates="subscriptions")
    __table_args__ = (
        UniqueConstraint("user_id", "search_hash", name="_user_search_uc"),
    )


class Ad(Base):
    __tablename__ = "ads"
    url: Mapped[str] = mapped_column(String, primary_key=True)
    ad_id: Mapped[str] = mapped_column(String, index=True)
    platform: Mapped[str] = mapped_column(String(10))
    data: Mapped[dict] = mapped_column(JSON)
    found_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SentAd(Base):
    __tablename__ = "sent_ads"
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id"), primary_key=True
    )
    ad_url: Mapped[str] = mapped_column(ForeignKey("ads.url"), primary_key=True)
