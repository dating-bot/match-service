from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import final, override

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from match_service.adapters.postgres_models.models import ConversationORM, MatchORM
from match_service.domain.match import Conversation, Match
from match_service.infra.postgres import AsyncSessionFactory
from match_service.protocols.match.repository import MatchRepositoryProtocol

log = structlog.stdlib.get_logger("match_service.adapters.match.postgres")


def _canonical(a: int, b: int) -> tuple[int, int]:
    """Return (user1, user2) in canonical order (smaller first)."""
    return (a, b) if a < b else (b, a)


@final
class PostgresMatchRepositoryAdapter(MatchRepositoryProtocol[AsyncSession]):
    def __init__(self, *, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    @override
    @asynccontextmanager
    async def context(self) -> AsyncGenerator[AsyncSession]:
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @override
    async def insert_match(
        self,
        session: AsyncSession,
        request: MatchRepositoryProtocol.InsertMatchRequest,
    ) -> tuple[Match, Conversation]:
        u1, u2 = _canonical(request.user1_telegram_id, request.user2_telegram_id)
        match_result = await session.execute(
            sa
            .insert(MatchORM)
            .values(user1_telegram_id=u1, user2_telegram_id=u2)
            .returning(MatchORM.id, MatchORM.user1_telegram_id, MatchORM.user2_telegram_id, MatchORM.created_at)
        )
        match_row = match_result.mappings().one()
        match = MatchORM(**dict(match_row)).to_domain()

        conv_result = await session.execute(
            sa
            .insert(ConversationORM)
            .values(match_id=match.id)
            .returning(ConversationORM.id, ConversationORM.match_id, ConversationORM.status, ConversationORM.created_at)
        )
        conv_row = conv_result.mappings().one()
        conversation = ConversationORM(**dict(conv_row)).to_domain()

        log.debug("match created", match_id=match.id, user1=u1, user2=u2)
        return match, conversation

    @override
    async def get_match_by_users(
        self,
        session: AsyncSession,
        user1_telegram_id: int,
        user2_telegram_id: int,
    ) -> Match | None:
        u1, u2 = _canonical(user1_telegram_id, user2_telegram_id)
        result = await session.execute(
            sa.select(MatchORM).where(
                MatchORM.user1_telegram_id == u1,
                MatchORM.user2_telegram_id == u2,
            )
        )
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm is not None else None

    @override
    async def list_matches_by_user(self, session: AsyncSession, telegram_id: int) -> list[Match]:
        result = await session.execute(
            sa
            .select(MatchORM)
            .where(
                sa.or_(
                    MatchORM.user1_telegram_id == telegram_id,
                    MatchORM.user2_telegram_id == telegram_id,
                )
            )
            .order_by(MatchORM.created_at.desc())
        )
        return [row.to_domain() for row in result.scalars().all()]

    @override
    async def get_conversation_by_match(self, session: AsyncSession, match_id: int) -> Conversation | None:
        result = await session.execute(sa.select(ConversationORM).where(ConversationORM.match_id == match_id))
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm is not None else None
