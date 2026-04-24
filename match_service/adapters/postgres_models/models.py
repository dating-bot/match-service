import uuid
from datetime import UTC, datetime
from typing import final

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from match_service.domain.interaction import InteractionStaging
from match_service.domain.like import Like, LikeStatus
from match_service.domain.match import Conversation, ConversationStatus, Match
from match_service.domain.outbox import OutboxEvent, OutboxEventStatus


class Base(DeclarativeBase):
    pass


@final
class LikeORM(Base):
    __tablename__: str = "likes"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    liker_telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    liked_telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )

    __table_args__: tuple[sa.UniqueConstraint, sa.Index, sa.Index] = (
        sa.UniqueConstraint("liker_telegram_id", "liked_telegram_id", name="uq_likes_liker_liked"),
        sa.Index("ix_likes_liker_telegram_id", "liker_telegram_id"),
        sa.Index("ix_likes_liked_telegram_id", "liked_telegram_id"),
    )

    def to_domain(self) -> Like:
        return Like(
            id=self.id,
            liker_telegram_id=self.liker_telegram_id,
            liked_telegram_id=self.liked_telegram_id,
            status=LikeStatus(self.status),
            created_at=self.created_at,
        )


@final
class MatchORM(Base):
    __tablename__: str = "matches"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    user1_telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    user2_telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    match_last_activity: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )
    ghost_warning_sent: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, server_default=sa.false())
    is_stale: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, server_default=sa.false())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )

    __table_args__: tuple[sa.UniqueConstraint, sa.CheckConstraint, sa.Index, sa.Index] = (
        sa.UniqueConstraint("user1_telegram_id", "user2_telegram_id", name="uq_matches_user1_user2"),
        sa.CheckConstraint("user1_telegram_id < user2_telegram_id", name="ck_matches_user_order"),
        sa.Index("ix_matches_user1_telegram_id", "user1_telegram_id"),
        sa.Index("ix_matches_user2_telegram_id", "user2_telegram_id"),
    )

    def to_domain(self) -> Match:
        return Match(
            id=self.id,
            user1_telegram_id=self.user1_telegram_id,
            user2_telegram_id=self.user2_telegram_id,
            match_last_activity=self.match_last_activity,
            ghost_warning_sent=self.ghost_warning_sent,
            is_stale=self.is_stale,
            created_at=self.created_at,
        )


@final
class ConversationORM(Base):
    __tablename__: str = "conversations"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        sa.BigInteger(),
        sa.ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )

    __table_args__: tuple[sa.UniqueConstraint, sa.Index] = (
        sa.UniqueConstraint("match_id", name="uq_conversations_match_id"),
        sa.Index("ix_conversations_match_id", "match_id"),
    )

    def to_domain(self) -> Conversation:
        return Conversation(
            id=self.id,
            match_id=self.match_id,
            status=ConversationStatus(self.status),
            created_at=self.created_at,
        )


@final
class OutboxEventORM(Base):
    __tablename__: str = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(postgresql.JSONB(), nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="PENDING")
    attempts: Mapped[int] = mapped_column(sa.Integer(), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )

    __table_args__: tuple[sa.Index] = (sa.Index("ix_outbox_events_status_created_at", "status", "created_at"),)

    def to_domain(self) -> OutboxEvent:
        return OutboxEvent(
            id=self.id,
            event_type=self.event_type,
            payload=self.payload,
            status=OutboxEventStatus(self.status),
            attempts=self.attempts,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@final
class InteractionStagingORM(Base):
    __tablename__: str = "interaction_staging"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    actor_telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    target_telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )

    __table_args__: tuple[sa.Index, sa.Index] = (
        sa.Index("ix_interaction_staging_actor", "actor_telegram_id"),
        sa.Index("ix_interaction_staging_target", "target_telegram_id"),
    )

    def to_domain(self) -> InteractionStaging:
        return InteractionStaging(
            id=self.id,
            actor_telegram_id=self.actor_telegram_id,
            target_telegram_id=self.target_telegram_id,
            created_at=self.created_at,
        )
