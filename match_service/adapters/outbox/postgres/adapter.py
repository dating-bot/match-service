import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import final, override

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from match_service.adapters.postgres_models.models import OutboxEventORM
from match_service.domain.outbox import OutboxEvent, OutboxEventStatus
from match_service.infra.postgres import AsyncSessionFactory
from match_service.protocols.outbox.repository import OutboxRepositoryProtocol

log = structlog.stdlib.get_logger("match_service.adapters.outbox.postgres")


@final
class PostgresOutboxRepositoryAdapter(OutboxRepositoryProtocol[AsyncSession]):
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
    async def insert_event(
        self,
        session: AsyncSession,
        request: OutboxRepositoryProtocol.InsertEventRequest,
    ) -> OutboxEvent:
        event_id = uuid.uuid4()
        result = await session.execute(
            sa
            .insert(OutboxEventORM)
            .values(
                id=event_id,
                event_type=request.event_type,
                payload=request.payload,
                status=OutboxEventStatus.PENDING.value,
            )
            .returning(
                OutboxEventORM.id,
                OutboxEventORM.event_type,
                OutboxEventORM.payload,
                OutboxEventORM.status,
                OutboxEventORM.attempts,
                OutboxEventORM.created_at,
                OutboxEventORM.updated_at,
            )
        )
        row = result.mappings().one()
        event = OutboxEventORM(**dict(row)).to_domain()
        log.debug("outbox event created", event_id=event.id, event_type=event.event_type)
        return event

    @override
    async def get_pending_events(self, session: AsyncSession, *, limit: int = 100) -> list[OutboxEvent]:
        result = await session.execute(
            sa
            .select(OutboxEventORM)
            .where(OutboxEventORM.status == OutboxEventStatus.PENDING.value)
            .order_by(OutboxEventORM.created_at)
            .limit(limit)
        )
        return [row.to_domain() for row in result.scalars().all()]

    @override
    async def mark_running(self, session: AsyncSession, event_id: uuid.UUID) -> None:
        await session.execute(
            sa
            .update(OutboxEventORM)
            .where(OutboxEventORM.id == event_id)
            .values(status=OutboxEventStatus.RUNNING.value, updated_at=datetime.now(UTC))
        )
        log.debug("outbox event marked running", event_id=event_id)

    @override
    async def mark_done(self, session: AsyncSession, event_id: uuid.UUID) -> None:
        await session.execute(
            sa
            .update(OutboxEventORM)
            .where(OutboxEventORM.id == event_id)
            .values(status=OutboxEventStatus.DONE.value, updated_at=datetime.now(UTC))
        )
        log.debug("outbox event marked done", event_id=event_id)

    @override
    async def mark_failed(self, session: AsyncSession, event_id: uuid.UUID) -> None:
        await session.execute(
            sa
            .update(OutboxEventORM)
            .where(OutboxEventORM.id == event_id)
            .values(
                status=OutboxEventStatus.FAILED.value,
                attempts=OutboxEventORM.attempts + 1,
                updated_at=datetime.now(UTC),
            )
        )
        log.debug("outbox event marked failed", event_id=event_id)
