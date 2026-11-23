"""SQLAlchemy mappings for users, dialog sessions, catalog assets, pairs and quotes."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class DialogSessionModel(Base):
    """At most one persistent dialog session per user; version supports optimistic locking."""

    __tablename__ = "dialog_sessions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_dialog_sessions_version_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE", name="fk_dialog_sessions_user_id_users"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'idle'"))
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AssetModel(Base):
    __tablename__ = "assets"
    __table_args__ = (CheckConstraint("kind IN ('fiat', 'crypto')", name="ck_assets_kind"),)

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    kind: Mapped[str] = mapped_column(String(6), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class PairModel(Base):
    __tablename__ = "pairs"
    __table_args__ = (
        UniqueConstraint("base_code", "quote_code", name="uq_pairs_base_quote"),
        CheckConstraint("base_code <> quote_code", name="ck_pairs_distinct_assets"),
        CheckConstraint("kind IN ('fiat', 'crypto')", name="ck_pairs_kind"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    base_code: Mapped[str] = mapped_column(ForeignKey("assets.code", name="fk_pairs_base_code_assets"), nullable=False)
    quote_code: Mapped[str] = mapped_column(ForeignKey("assets.code", name="fk_pairs_quote_code_assets"), nullable=False)
    kind: Mapped[str] = mapped_column(String(6), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class QuoteModel(Base):
    """A point in one independent time series (live or hourly)."""

    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint("series_kind IN ('live', 'hour')", name="ck_quotes_series_kind"),
        CheckConstraint("price > 0", name="ck_quotes_price_positive"),
        Index("ix_quotes_pair_series_quoted_at", "pair_id", "series_kind", "quoted_at"),
    )

    pair_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pairs.id", ondelete="CASCADE", name="fk_quotes_pair_id_pairs"), primary_key=True
    )
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    series_kind: Mapped[str] = mapped_column(String(4), primary_key=True)
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # No precision/scale is specified intentionally: PostgreSQL NUMERIC stays exact.
    price: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)
