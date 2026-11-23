"""Idempotent seed/reload operations for the supported assets and pair catalogue."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import AssetModel, PairModel


# Supported by the functional requirements and HLD external-provider contracts:
# BTC/ETH are the crypto base assets; RUB/USD/EUR are quote currencies.
ASSETS: tuple[dict[str, object], ...] = (
    {"code": "RUB", "kind": "fiat", "provider_id": None, "enabled": True},
    {"code": "USD", "kind": "fiat", "provider_id": None, "enabled": True},
    {"code": "EUR", "kind": "fiat", "provider_id": None, "enabled": True},
    {"code": "BTC", "kind": "crypto", "provider_id": "bitcoin", "enabled": True},
    {"code": "ETH", "kind": "crypto", "provider_id": "ethereum", "enabled": True},
)


def _pair_id(base_code: str, quote_code: str) -> UUID:
    """Return a deterministic ID that is identical in migrations and reloads."""
    return uuid5(NAMESPACE_URL, f"kurs-mayak:pair:{base_code}/{quote_code}")


def _build_pairs() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    fiat_codes = ("RUB", "USD", "EUR")
    crypto_codes = ("BTC", "ETH")

    for base_code in fiat_codes:
        for quote_code in fiat_codes:
            if base_code != quote_code:
                rows.append(
                    {
                        "id": _pair_id(base_code, quote_code),
                        "base_code": base_code,
                        "quote_code": quote_code,
                        "kind": "fiat",
                        "enabled": True,
                    }
                )

    for base_code in crypto_codes:
        for quote_code in fiat_codes:
            rows.append(
                {
                    "id": _pair_id(base_code, quote_code),
                    "base_code": base_code,
                    "quote_code": quote_code,
                    "kind": "crypto",
                    "enabled": True,
                }
            )
    return tuple(rows)


PAIRS: tuple[dict[str, object], ...] = _build_pairs()


async def seed_catalog(session: AsyncSession) -> None:
    """Insert or refresh known catalogue metadata without duplicating natural keys.

    The function is safe to call repeatedly. Existing `enabled` flags are preserved
    so an operator's manual disable action is not undone by a catalogue reload.
    Assets are always upserted before pairs to satisfy the pair foreign keys.
    The caller owns the transaction and commits/rolls it back.
    """
    asset_insert = insert(AssetModel).values(list(ASSETS))
    await session.execute(
        asset_insert.on_conflict_do_update(
            index_elements=[AssetModel.code],
            set_={
                "kind": asset_insert.excluded.kind,
                "provider_id": asset_insert.excluded.provider_id,
            },
        )
    )

    pair_insert = insert(PairModel).values(list(PAIRS))
    await session.execute(
        pair_insert.on_conflict_do_update(
            index_elements=[PairModel.base_code, PairModel.quote_code],
            set_={"kind": pair_insert.excluded.kind},
        )
    )
