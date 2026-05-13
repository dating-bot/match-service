from dataclasses import dataclass
from datetime import UTC, datetime
from typing import final

import structlog
import structlog.contextvars
from sqlalchemy.exc import IntegrityError

from match_service.domain.like import Like, LikeStatus
from match_service.domain.match import Match
from match_service.infra.valkey import ValkeyClient
from match_service.protocols.like.repository import LikeRepositoryProtocol
from match_service.protocols.match.repository import MatchRepositoryProtocol
from match_service.protocols.outbox.repository import OutboxRepositoryProtocol

log = structlog.stdlib.get_logger("match_service.usecases.HandleLike")

MATCH_CREATED_EVENT = "match.created"
LIKE_RECEIVED_EVENT = "like.received"


class HandleLikeError(Exception):
    """Base exception for HandleLike usecase."""


class HandleLikeDuplicateError(HandleLikeError):
    """Like from this user to target already exists."""


@final
class HandleLike[SessionT]:
    def __init__(
        self,
        *,
        like_repository: LikeRepositoryProtocol[SessionT],
        match_repository: MatchRepositoryProtocol[SessionT],
        outbox_repository: OutboxRepositoryProtocol[SessionT],
        valkey: ValkeyClient,
        match_debounce_ttl: int,
    ) -> None:
        self._like_repository = like_repository
        self._match_repository = match_repository
        self._outbox_repository = outbox_repository
        self._valkey = valkey
        self._match_debounce_ttl = match_debounce_ttl

    @dataclass
    class Request:
        liker_telegram_id: int
        liked_telegram_id: int
        status: LikeStatus = LikeStatus.LIKED

    @dataclass
    class Response:
        like: Like
        match: Match | None = None
        is_new_match: bool = False

    async def execute(self, request: Request) -> Response:
        match: Match | None = None
        is_new_match = False
        trace_id = str(structlog.contextvars.get_contextvars().get("trace_id") or "")

        async with self._like_repository.context() as session:
            like = await self._insert_like(session, request)

            _ = await self._outbox_repository.insert_event(
                session,
                OutboxRepositoryProtocol.InsertEventRequest(
                    event_type=LIKE_RECEIVED_EVENT,
                    payload={
                        "liker_telegram_id": request.liker_telegram_id,
                        "liked_telegram_id": request.liked_telegram_id,
                        "status": request.status.value,
                        "trace_id": trace_id,
                    },
                ),
            )

            is_mutual = await self._like_repository.exists_reverse_like(
                session,
                request.liker_telegram_id,
                request.liked_telegram_id,
            )
            if is_mutual:
                match, _ = await self._match_repository.insert_match(
                    session,
                    MatchRepositoryProtocol.InsertMatchRequest(
                        user1_telegram_id=request.liker_telegram_id,
                        user2_telegram_id=request.liked_telegram_id,
                    ),
                )
                _ = await self._outbox_repository.insert_event(
                    session,
                    OutboxRepositoryProtocol.InsertEventRequest(
                        event_type=MATCH_CREATED_EVENT,
                        payload={
                            "match_id": match.id,
                            "user1_telegram_id": match.user1_telegram_id,
                            "user2_telegram_id": match.user2_telegram_id,
                            "trace_id": trace_id,
                        },
                    ),
                )
                is_new_match = True
                log.info(
                    "match created",
                    match_id=match.id,
                    user1=match.user1_telegram_id,
                    user2=match.user2_telegram_id,
                )

        if match is not None:
            match_activity_ts = datetime.now(UTC).isoformat()
            await self._valkey.set(
                f"match_activity:{match.id}",
                match_activity_ts,
                nx=True,
                ex=self._match_debounce_ttl,
            )

        log.debug(
            "like handled",
            liker=request.liker_telegram_id,
            liked=request.liked_telegram_id,
            is_new_match=is_new_match,
        )
        return self.Response(like=like, match=match, is_new_match=is_new_match)

    async def _insert_like(self, session: SessionT, request: Request) -> Like:
        try:
            return await self._like_repository.insert_like(
                session,
                LikeRepositoryProtocol.InsertLikeRequest(
                    liker_telegram_id=request.liker_telegram_id,
                    liked_telegram_id=request.liked_telegram_id,
                    status=request.status,
                ),
            )
        except IntegrityError as e:
            msg = f"Like from {request.liker_telegram_id} to {request.liked_telegram_id} already exists"
            raise HandleLikeDuplicateError(msg) from e
