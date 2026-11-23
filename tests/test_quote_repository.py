from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from contracts import Quote
from infrastructure.db.models import QuoteModel
from infrastructure.db.quote_repository import PostgresQuoteRepository

PAIR_ID = UUID("00000000-0000-0000-0000-000000000001")
T0 = datetime(2026, 11, 23, 12, tzinfo=UTC)


def make_quote(price: str = "123.4567890123456789") -> Quote:
    return Quote(PAIR_ID, Decimal(price), "provider", T0, T0)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["live", "hour"])
async def test_save_uses_idempotent_composite_upsert_and_series_kind(kind: str) -> None:
    session = AsyncMock()
    repository = PostgresQuoteRepository(session)

    await repository.save([make_quote()], kind=kind)  # type: ignore[arg-type]

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql
    assert "series_kind" in sql
    assert "DO UPDATE SET" in sql
    assert statement.compile(dialect=postgresql.dialect()).params["series_kind_m0"] == kind


@pytest.mark.asyncio
async def test_empty_save_does_not_issue_database_query() -> None:
    session = AsyncMock()
    repository = PostgresQuoteRepository(session)

    await repository.save([], kind="live")

    session.execute.assert_not_awaited()


def test_quote_column_types_and_composite_primary_key() -> None:
    table = QuoteModel.__table__
    assert table.c.price.type.__class__.__name__ == "Numeric"
    assert table.c.price.type.precision is None
    assert table.c.price.type.scale is None
    assert table.c.quoted_at.type.timezone is True
    assert table.c.received_at.type.timezone is True
    assert {column.name for column in table.primary_key.columns} == {
        "pair_id", "source", "series_kind", "quoted_at"
    }
    assert table.c.series_kind.type.length == 4


def test_live_and_hour_are_distinct_unique_points() -> None:
    # The discriminator is part of the DB key and the ON CONFLICT target.
    key = ["pair_id", "source", "series_kind", "quoted_at"]
    assert [column.name for column in QuoteModel.__table__.primary_key.columns] == key


@pytest.mark.asyncio
async def test_latest_filters_by_requested_series() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repository = PostgresQuoteRepository(session)

    assert await repository.latest(PAIR_ID, kind="live") is None

    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "series_kind" in str(compiled)
    assert "live" in compiled.params.values()


@pytest.mark.asyncio
async def test_get_series_filters_kind_and_both_inclusive_boundaries() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    repository = PostgresQuoteRepository(session)

    assert await repository.get_series(PAIR_ID, T0, T0, kind="hour") == []

    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "series_kind" in sql and "quoted_at" in sql
    assert "hour" in compiled.params.values()
    assert sum(value == T0 for value in compiled.params.values()) == 2
