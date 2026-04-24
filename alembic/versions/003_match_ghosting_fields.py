# pyright: reportUnusedCallResult=false
"""add anti-ghosting fields to matches

Revision ID: 003
Revises: 002
Create Date: 2026-04-23 00:00:00.000000+03:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "matches",
        sa.Column("match_last_activity", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "matches",
        sa.Column("ghost_warning_sent", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "matches",
        sa.Column("is_stale", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("matches", "is_stale")
    op.drop_column("matches", "ghost_warning_sent")
    op.drop_column("matches", "match_last_activity")
