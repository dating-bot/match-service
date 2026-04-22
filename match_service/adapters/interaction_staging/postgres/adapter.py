from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import final, override

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from match_service.adapters.postgres_models.models import InteractionStagingORM
from match_service.domain.interaction import InteractionStaging
from match_service.infra.postgres import AsyncSessionFactory
from match_service.protocols.interaction_staging.repository import InteractionStagingRepositoryProtocol

log = structlog.stdlib.get_logger("match_service.adapters.interaction_staging.postgres")


@final
class PostgresInteractionStagingRepositoryAdapter(InteractionStagingRepositoryProtocol[AsyncSession]):
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
    async def insert_staging(
        self,
        session: AsyncSession,
        request: InteractionStagingRepositoryProtocol.InsertStagingRequest,
    ) -> InteractionStaging:
        result = await session.execute(
            sa.insert(InteractionStagingORM)
            .values(
                actor_telegram_id=request.actor_telegram_id,
                target_telegram_id=request.target_telegram_id,
            )
            .returning(
                InteractionStagingORM.id,
                InteractionStagingORM.actor_telegram_id,
                InteractionStagingORM.target_telegram_id,
                InteractionStagingORM.created_at,
            )
        )
        row = result.mappings().one()
        staging = InteractionStagingORM(**dict(row)).to_domain()
        log.debug(
            "interaction staging inserted",
            actor_telegram_id=request.actor_telegram_id,
            target_telegram_id=request.target_telegram_id,
        )
        return staging
