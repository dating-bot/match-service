from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import final, override

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from match_service.adapters.postgres_models.models import LikeORM
from match_service.domain.like import Like
from match_service.infra.postgres import AsyncSessionFactory
from match_service.protocols.like.repository import LikeRepositoryProtocol

log = structlog.stdlib.get_logger("match_service.adapters.like.postgres")


@final
class PostgresLikeRepositoryAdapter(LikeRepositoryProtocol[AsyncSession]):
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
    async def insert_like(
        self,
        session: AsyncSession,
        request: LikeRepositoryProtocol.InsertLikeRequest,
    ) -> Like:
        result = await session.execute(
            sa
            .insert(LikeORM)
            .values(
                liker_telegram_id=request.liker_telegram_id,
                liked_telegram_id=request.liked_telegram_id,
                status=request.status.value,
            )
            .returning(
                LikeORM.id,
                LikeORM.liker_telegram_id,
                LikeORM.liked_telegram_id,
                LikeORM.status,
                LikeORM.created_at,
            )
        )
        row = result.mappings().one()
        like = LikeORM(**dict(row)).to_domain()
        log.debug(
            "like inserted",
            liker_telegram_id=request.liker_telegram_id,
            liked_telegram_id=request.liked_telegram_id,
            status=request.status,
        )
        return like

    @override
    async def exists_reverse_like(
        self,
        session: AsyncSession,
        liker_telegram_id: int,
        liked_telegram_id: int,
    ) -> bool:
        result = await session.execute(
            sa.select(
                sa.exists().where(
                    LikeORM.liker_telegram_id == liked_telegram_id,
                    LikeORM.liked_telegram_id == liker_telegram_id,
                )
            )
        )
        return bool(result.scalar())

    @override
    async def get_like(
        self,
        session: AsyncSession,
        liker_telegram_id: int,
        liked_telegram_id: int,
    ) -> Like | None:
        result = await session.execute(
            sa.select(LikeORM).where(
                LikeORM.liker_telegram_id == liker_telegram_id,
                LikeORM.liked_telegram_id == liked_telegram_id,
            )
        )
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm is not None else None

    @override
    async def list_sent_likes(self, session: AsyncSession, liker_telegram_id: int) -> list[Like]:
        result = await session.execute(
            sa.select(LikeORM).where(LikeORM.liker_telegram_id == liker_telegram_id).order_by(LikeORM.created_at)
        )
        return [row.to_domain() for row in result.scalars().all()]

    @override
    async def list_received_likes(self, session: AsyncSession, liked_telegram_id: int) -> list[Like]:
        result = await session.execute(
            sa.select(LikeORM).where(LikeORM.liked_telegram_id == liked_telegram_id).order_by(LikeORM.created_at)
        )
        return [row.to_domain() for row in result.scalars().all()]
