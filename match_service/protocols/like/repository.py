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
    class CreateLikeRequest:
        liker_telegram_id: int
        liked_telegram_id: int
        status: LikeStatus

    async def create_like(self, session: SessionT, request: CreateLikeRequest) -> Like: ...

    async def get_like(
        self,
        session: SessionT,
        liker_telegram_id: int,
        liked_telegram_id: int,
    ) -> Like | None: ...

    async def list_sent_likes(self, session: SessionT, liker_telegram_id: int) -> list[Like]: ...

    async def list_received_likes(self, session: SessionT, liked_telegram_id: int) -> list[Like]: ...
