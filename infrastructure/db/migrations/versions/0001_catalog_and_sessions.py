"""Create users, dialog sessions, the supported asset catalogue and pairs.

Revision ID: 0001_catalog_and_sessions
Revises:
Create Date: 2026-11-23
"""

from alembic import op
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_catalog_and_sessions"
down_revision = None
branch_labels = None
depends_on = None


_ASSETS = (
    {"code": "RUB", "kind": "fiat", "provider_id": None, "enabled": True},
    {"code": "USD", "kind": "fiat", "provider_id": None, "enabled": True},
    {"code": "EUR", "kind": "fiat", "provider_id": None, "enabled": True},
    {"code": "BTC", "kind": "crypto", "provider_id": "bitcoin", "enabled": True},
    {"code": "ETH", "kind": "crypto", "provider_id": "ethereum", "enabled": True},
)

# IDs are UUIDv5(NAMESPACE_URL, "kurs-mayak:pair:<BASE>/<QUOTE>"). They remain
# stable between a fresh migration and a subsequent catalogue reload.
_PAIRS = (
    ("426cc65e-647f-5d6d-8616-6f1fe47afb00", "RUB", "USD", "fiat"),
    ("faf896cc-ce13-5edb-b71e-4229fc849c6b", "RUB", "EUR", "fiat"),
    ("ee755087-a585-5979-a13e-0c92b9be03e6", "USD", "RUB", "fiat"),
    ("871e44a5-68dd-554f-99d0-8eba8509f816", "USD", "EUR", "fiat"),
    ("c36a2f5b-67e5-560e-ba20-f0f0604e1df3", "EUR", "RUB", "fiat"),
    ("9b419a25-72d7-5945-a600-47362ccaed58", "EUR", "USD", "fiat"),
    ("d962a068-affb-5091-9390-43f84e095eb7", "BTC", "RUB", "crypto"),
    ("ee047b25-40f7-5d40-b8c9-7828771ae3e7", "BTC", "USD", "crypto"),
    ("cc946aee-04d3-5333-9404-88839341c026", "BTC", "EUR", "crypto"),
    ("11051218-e3c9-52d0-97f0-05f4ccf1e292", "ETH", "RUB", "crypto"),
    ("c26e417a-faa7-54d4-b5a7-a14c62320aed", "ETH", "USD", "crypto"),
    ("131a8003-19d5-56d9-884c-72eb43334ec7", "ETH", "EUR", "crypto"),
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),
    )

    op.create_table(
        "dialog_sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("version >= 1", name="ck_dialog_sessions_version_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_dialog_sessions_user_id_users"),
        sa.PrimaryKeyConstraint("user_id", name="pk_dialog_sessions"),
    )

    op.create_table(
        "assets",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("kind", sa.String(length=6), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("kind IN ('fiat', 'crypto')", name="ck_assets_kind"),
        sa.PrimaryKeyConstraint("code", name="pk_assets"),
    )

    op.create_table(
        "pairs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_code", sa.String(length=8), nullable=False),
        sa.Column("quote_code", sa.String(length=8), nullable=False),
        sa.Column("kind", sa.String(length=6), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("base_code <> quote_code", name="ck_pairs_distinct_assets"),
        sa.CheckConstraint("kind IN ('fiat', 'crypto')", name="ck_pairs_kind"),
        sa.ForeignKeyConstraint(["base_code"], ["assets.code"], name="fk_pairs_base_code_assets"),
        sa.ForeignKeyConstraint(["quote_code"], ["assets.code"], name="fk_pairs_quote_code_assets"),
        sa.PrimaryKeyConstraint("id", name="pk_pairs"),
        sa.UniqueConstraint("base_code", "quote_code", name="uq_pairs_base_quote"),
    )

    # Seed assets first to satisfy pair foreign keys. ON CONFLICT makes this
    # safe if a catalogue seed is replayed manually during maintenance.
    assets_table = sa.table(
        "assets",
        sa.column("code", sa.String(8)),
        sa.column("kind", sa.String(6)),
        sa.column("provider_id", sa.Text()),
        sa.column("enabled", sa.Boolean()),
    )
    asset_insert = postgresql.insert(assets_table).values(list(_ASSETS))
    op.get_bind().execute(
        asset_insert.on_conflict_do_update(
            index_elements=[assets_table.c.code],
            set_={
                "kind": asset_insert.excluded.kind,
                "provider_id": asset_insert.excluded.provider_id,
            },
        )
    )

    pairs_table = sa.table(
        "pairs",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("base_code", sa.String(8)),
        sa.column("quote_code", sa.String(8)),
        sa.column("kind", sa.String(6)),
        sa.column("enabled", sa.Boolean()),
    )
    pair_rows = [
        {"id": UUID(pair_id), "base_code": base, "quote_code": quote, "kind": kind, "enabled": True}
        for pair_id, base, quote, kind in _PAIRS
    ]
    pair_insert = postgresql.insert(pairs_table).values(pair_rows)
    op.get_bind().execute(
        pair_insert.on_conflict_do_update(
            index_elements=[pairs_table.c.base_code, pairs_table.c.quote_code],
            set_={"kind": pair_insert.excluded.kind},
        )
    )


def downgrade() -> None:
    op.drop_table("pairs")
    op.drop_table("assets")
    op.drop_table("dialog_sessions")
    op.drop_table("users")
