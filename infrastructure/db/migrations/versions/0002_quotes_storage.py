"""Create the separated live and hourly quote time series.

Revision ID: 0002_quotes_storage
Revises: 0001_catalog_and_sessions
Create Date: 2026-11-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_quotes_storage"
down_revision = "0001_catalog_and_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("series_kind", sa.String(length=4), nullable=False),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.CheckConstraint("series_kind IN ('live', 'hour')", name="ck_quotes_series_kind"),
        sa.CheckConstraint("price > 0", name="ck_quotes_price_positive"),
        sa.ForeignKeyConstraint(["pair_id"], ["pairs.id"], ondelete="CASCADE", name="fk_quotes_pair_id_pairs"),
        sa.PrimaryKeyConstraint("pair_id", "source", "series_kind", "quoted_at", name="pk_quotes"),
    )
    op.create_index(
        "ix_quotes_pair_series_quoted_at",
        "quotes",
        ["pair_id", "series_kind", "quoted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_quotes_pair_series_quoted_at", table_name="quotes")
    op.drop_table("quotes")
