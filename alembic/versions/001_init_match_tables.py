# pyright: reportUnusedCallResult=false
"""init match tables

Revision ID: 001
Revises:
Create Date: 2026-04-22 00:00:00.000000+03:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "likes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("liker_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("liked_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("liker_telegram_id", "liked_telegram_id", name="uq_likes_liker_liked"),
    )
    op.create_index("ix_likes_liker_telegram_id", "likes", ["liker_telegram_id"])
    op.create_index("ix_likes_liked_telegram_id", "likes", ["liked_telegram_id"])

    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user1_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("user2_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user1_telegram_id", "user2_telegram_id", name="uq_matches_user1_user2"),
        sa.CheckConstraint("user1_telegram_id < user2_telegram_id", name="ck_matches_user_order"),
    )
    op.create_index("ix_matches_user1_telegram_id", "matches", ["user1_telegram_id"])
    op.create_index("ix_matches_user2_telegram_id", "matches", ["user2_telegram_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.BigInteger(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("match_id", name="uq_conversations_match_id"),
    )
    op.create_index("ix_conversations_match_id", "conversations", ["match_id"])

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outbox_events_status_created_at", "outbox_events", ["status", "created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_outbox_events_status_created_at", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.drop_index("ix_conversations_match_id", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_matches_user2_telegram_id", table_name="matches")
    op.drop_index("ix_matches_user1_telegram_id", table_name="matches")
    op.drop_table("matches")

    op.drop_index("ix_likes_liked_telegram_id", table_name="likes")
    op.drop_index("ix_likes_liker_telegram_id", table_name="likes")
    op.drop_table("likes")
