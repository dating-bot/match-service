from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from match_service.domain.match import Conversation, Match


class MatchRepositoryProtocol[SessionT](Protocol):
    @asynccontextmanager
    async def context(self) -> AsyncGenerator[SessionT]:
        raise NotImplementedError
        yield  # pyright: ignore[reportUnreachable]

    @dataclass
    class CreateMatchRequest:
        user1_telegram_id: int
        user2_telegram_id: int

    async def create_match(self, session: SessionT, request: CreateMatchRequest) -> tuple[Match, Conversation]: ...

    async def get_match_by_users(
        self,
        session: SessionT,
        user1_telegram_id: int,
        user2_telegram_id: int,
    ) -> Match | None: ...

    async def list_matches_by_user(self, session: SessionT, telegram_id: int) -> list[Match]: ...

    async def get_conversation_by_match(self, session: SessionT, match_id: int) -> Conversation | None: ...
