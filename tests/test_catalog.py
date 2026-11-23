from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from infrastructure.db.catalog import ASSETS, PAIRS, seed_catalog
from infrastructure.db.models import AssetModel, DialogSessionModel, PairModel, UserModel


@pytest.mark.asyncio
async def test_catalog_seed_is_repeatable_and_uses_natural_key_upserts() -> None:
    session = AsyncMock()

    await seed_catalog(session)
    await seed_catalog(session)

    assert session.execute.await_count == 4
    statements = [call.args[0] for call in session.execute.await_args_list]
    compiled = [statement.compile(dialect=postgresql.dialect()) for statement in statements]

    # Each seed run writes assets before pairs and uses conflict-safe upserts.
    assert 'INSERT INTO assets' in str(compiled[0])
    assert 'ON CONFLICT (code) DO UPDATE' in str(compiled[0])
    assert 'INSERT INTO pairs' in str(compiled[1])
    assert 'ON CONFLICT (base_code, quote_code) DO UPDATE' in str(compiled[1])
    assert 'INSERT INTO assets' in str(compiled[2])
    assert 'INSERT INTO pairs' in str(compiled[3])
    assert len(ASSETS) == 5
    assert len(PAIRS) == 12


def test_catalog_contains_only_supported_assets_and_pair_shapes() -> None:
    assets = {item['code']: item for item in ASSETS}
    assert set(assets) == {'RUB', 'USD', 'EUR', 'BTC', 'ETH'}
    assert assets['BTC']['provider_id'] == 'bitcoin'
    assert assets['ETH']['provider_id'] == 'ethereum'

    pairs = {(item['base_code'], item['quote_code']): item['kind'] for item in PAIRS}
    assert len(pairs) == len(PAIRS)
    assert all(base != quote for base, quote in pairs)
    assert all(kind == 'fiat' for (base, quote), kind in pairs.items() if base in {'RUB', 'USD', 'EUR'})
    assert all(kind == 'crypto' for (base, _), kind in pairs.items() if base in {'BTC', 'ETH'})
    assert not any(base in {'BTC', 'ETH'} and quote in {'BTC', 'ETH'} for base, quote in pairs)


def test_user_and_dialog_session_schema_matches_hld_one_to_one_key() -> None:
    user = UserModel.__table__
    session = DialogSessionModel.__table__

    assert user.c.telegram_user_id.type.__class__.__name__ == 'BigInteger'
    assert user.c.chat_id.type.__class__.__name__ == 'BigInteger'
    assert any(
        {column.name for column in constraint.columns} == {'telegram_user_id'}
        for constraint in user.constraints
        if constraint.__class__.__name__ == 'UniqueConstraint'
    )
    assert list(session.primary_key.columns.keys()) == ['user_id']
    assert session.c.user_id.foreign_keys
    assert session.c.version.type.__class__.__name__ == 'BigInteger'
    assert session.c.payload.type.__class__.__name__ == 'JSONB'


def test_pair_catalog_has_unique_ordered_pair_and_asset_foreign_keys() -> None:
    table = PairModel.__table__
    assert any(
        [column.name for column in constraint.columns] == ['base_code', 'quote_code']
        for constraint in table.constraints
        if constraint.__class__.__name__ == 'UniqueConstraint'
    )
    assert table.c.base_code.foreign_keys
    assert table.c.quote_code.foreign_keys
