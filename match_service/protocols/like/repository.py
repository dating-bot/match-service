from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from match_service.domain.like import Like, LikeStatus


class LikeRepositoryProtocol[SessionT](Protocol):
    @asynccontextmanager
    async def context(self) -> AsyncGenerator[SessionT]:
        raise NotImplementedError
        yield  # pyright: ignore[reportUnreachable]

    @dataclass
    class InsertLikeRequest:
        liker_telegram_id: int
        liked_telegram_id: int
        status: LikeStatus

    async def insert_like(self, session: SessionT, request: InsertLikeRequest) -> Like: ...

    async def exists_reverse_like(
        self,
        session: SessionT,
        liker_telegram_id: int,
        liked_telegram_id: int,
    ) -> bool:
        """Return True if liked_telegram_id has already liked liker_telegram_id."""
        ...

    async def get_like(
        self,
        session: SessionT,
        liker_telegram_id: int,
        liked_telegram_id: int,
    ) -> Like | None: ...

    async def list_sent_likes(self, session: SessionT, liker_telegram_id: int) -> list[Like]: ...

    async def list_received_likes(self, session: SessionT, liked_telegram_id: int) -> list[Like]: ...
