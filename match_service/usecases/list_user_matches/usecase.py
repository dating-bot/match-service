from typing import final

import pydantic
import structlog

from match_service.protocols.match.repository import MatchRepositoryProtocol

log = structlog.stdlib.get_logger("match_service.usecases.ListUserMatches")


@final
class ListUserMatches[SessionT]:
    def __init__(self, *, match_repository: MatchRepositoryProtocol[SessionT]) -> None:
        self._match_repository = match_repository

    class Request(pydantic.BaseModel):
        """Request to list recent matches for a user."""

        telegram_id: int
        limit: int = 20

    class UserMatch(pydantic.BaseModel):
        match_id: int
        other_telegram_id: int

    class Response(pydantic.BaseModel):
        matches: list["ListUserMatches.UserMatch"]

    async def execute(self, request: Request) -> Response:
        """Load matches from DB, map to the other party's telegram id."""
        if request.limit < 1:
            return ListUserMatches.Response(matches=[])

        async with self._match_repository.context() as session:
            raw = await self._match_repository.list_matches_by_user(session, request.telegram_id)

        out: list[ListUserMatches.UserMatch] = []
        for m in raw[: request.limit]:
            other = m.user2_telegram_id if m.user1_telegram_id == request.telegram_id else m.user1_telegram_id
            out.append(ListUserMatches.UserMatch(match_id=m.id, other_telegram_id=other))

        log.debug("list_user_matches", telegram_id=request.telegram_id, count=len(out))
        return ListUserMatches.Response(matches=out)
