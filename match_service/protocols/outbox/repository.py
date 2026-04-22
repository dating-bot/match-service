import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Protocol

from match_service.domain.outbox import OutboxEvent


class OutboxRepositoryProtocol[SessionT](Protocol):
    @asynccontextmanager
    async def context(self) -> AsyncGenerator[SessionT]:
        raise NotImplementedError
        yield  # pyright: ignore[reportUnreachable]

    @dataclass
    class InsertEventRequest:
        event_type: str
        payload: dict[str, object] = field(default_factory=dict)

    async def insert_event(self, session: SessionT, request: InsertEventRequest) -> OutboxEvent: ...

    async def get_pending_events(self, session: SessionT, *, limit: int = 100) -> list[OutboxEvent]: ...

    async def mark_running(self, session: SessionT, event_id: uuid.UUID) -> None: ...

    async def mark_done(self, session: SessionT, event_id: uuid.UUID) -> None: ...

    async def mark_failed(self, session: SessionT, event_id: uuid.UUID) -> None: ...
