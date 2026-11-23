"""Async PostgreSQL implementation of QuoteRepository."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from contracts import AssetPair, Quote, SeriesKind
from infrastructure.db.models import PairModel, QuoteModel


class PostgresQuoteRepository:
    """Persists live and hourly series under separate uniqueness namespaces."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pair(self, pair_id: UUID) -> AssetPair | None:
        statement = select(PairModel).where(PairModel.id == pair_id)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        if row is None:
            return None
        return AssetPair(row.id, row.base_code, row.quote_code, row.kind)

    @staticmethod
    def _to_contract(row: QuoteModel) -> Quote:
        return Quote(
            pair_id=row.pair_id,
            price=row.price,
            source=row.source,
            quoted_at=row.quoted_at,
            received_at=row.received_at,
        )

    async def latest(self, pair_id: UUID, *, kind: SeriesKind) -> Quote | None:
        if kind not in ("live", "hour"):
            raise ValueError("Неизвестный тип ряда котировок")
        statement = (
            select(QuoteModel)
            .where(QuoteModel.pair_id == pair_id, QuoteModel.series_kind == kind)
            .order_by(
                QuoteModel.quoted_at.desc(),
                QuoteModel.received_at.desc(),
                QuoteModel.source,
            )
            .limit(1)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return self._to_contract(row) if row is not None else None

    async def get_series(
        self, pair_id: UUID, start: datetime, end: datetime, *, kind: SeriesKind
    ) -> Sequence[Quote]:
        if kind not in ("live", "hour"):
            raise ValueError("Неизвестный тип ряда котировок")
        if start.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("Границы периода должны содержать часовой пояс")
        if start > end:
            raise ValueError("Начало периода не может быть позже окончания")
        statement = (
            select(QuoteModel)
            .where(
                QuoteModel.pair_id == pair_id,
                QuoteModel.series_kind == kind,
                QuoteModel.quoted_at >= start,
                QuoteModel.quoted_at <= end,
            )
            .order_by(QuoteModel.quoted_at, QuoteModel.source)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [self._to_contract(row) for row in rows]

    async def save(self, quotes: Sequence[Quote], *, kind: SeriesKind) -> None:
        """Insert or replace the exact point; repeating the same write is safe.

        The conflict target includes series_kind, so an hourly point can never
        update/delete/replace a live point even if all other key fields match.
        """
        if kind not in ("live", "hour"):
            raise ValueError("Неизвестный тип ряда котировок")
        if not quotes:
            return
        values: list[dict[str, object]] = []
        for quote in quotes:
            if quote.quoted_at.utcoffset() is None or quote.received_at.utcoffset() is None:
                raise ValueError("Время котировки и получения должно содержать часовой пояс")
            values.append(
                {
                    "pair_id": quote.pair_id,
                    "source": quote.source,
                    "series_kind": kind,
                    "quoted_at": quote.quoted_at,
                    "received_at": quote.received_at,
                    "price": quote.price,
                }
            )
        statement = insert(QuoteModel).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[
                QuoteModel.pair_id,
                QuoteModel.source,
                QuoteModel.series_kind,
                QuoteModel.quoted_at,
            ],
            set_={
                "price": statement.excluded.price,
                "received_at": statement.excluded.received_at,
            },
        )
        await self._session.execute(statement)
