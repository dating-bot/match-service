# pyright: reportUnusedCallResult=false
"""add interaction_staging

Revision ID: 002
Revises: 001
Create Date: 2026-04-22 00:00:00.000000+03:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "interaction_staging",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_interaction_staging_actor", "interaction_staging", ["actor_telegram_id"])
    op.create_index("ix_interaction_staging_target", "interaction_staging", ["target_telegram_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_interaction_staging_target", table_name="interaction_staging")
    op.drop_index("ix_interaction_staging_actor", table_name="interaction_staging")
    op.drop_table("interaction_staging")
