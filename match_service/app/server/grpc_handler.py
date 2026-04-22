from dataclasses import dataclass
from typing import final, override

import structlog
from grpclib import Status
from grpclib.exceptions import GRPCError
from sqlalchemy.ext.asyncio import AsyncSession

from match_api.v1 import match_pb2
from match_api.v1.match_grpc import MatchServiceBase
from match_service.app.server.utils.unary import unary
from match_service.domain.like import LikeStatus
from match_service.usecases import HandleLike, HandleLikeDuplicateError, HandleLikeError, HandleSkip

log = structlog.stdlib.get_logger("match_service.grpc")


@final
@dataclass(slots=True)
class MatchServiceHandler(MatchServiceBase):
    _handle_like: HandleLike[AsyncSession]
    _handle_skip: HandleSkip[AsyncSession]

    @override
    @unary
    async def Health(self, request: match_pb2.HealthRequest) -> match_pb2.HealthResponse:
        return match_pb2.HealthResponse(ok=True)

    @override
    @unary
    async def HandleLike(self, request: match_pb2.HandleLikeRequest) -> match_pb2.HandleLikeResponse:
        if not request.liker_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "liker_id is required")
        if not request.liked_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "liked_id is required")

        try:
            result = await self._handle_like.execute(
                HandleLike.Request(
                    liker_telegram_id=request.liker_id,
                    liked_telegram_id=request.liked_id,
                    status=LikeStatus.LIKED,
                )
            )
        except HandleLikeDuplicateError as e:
            raise GRPCError(Status.ALREADY_EXISTS, str(e)) from e
        except HandleLikeError as e:
            log.exception("error in HandleLike", liker_id=request.liker_id, liked_id=request.liked_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        response = match_pb2.HandleLikeResponse(matched=result.is_new_match)
        if result.match is not None:
            response.match_id = result.match.id

        return response

    @override
    @unary
    async def HandleSkip(self, request: match_pb2.HandleSkipRequest) -> match_pb2.HandleSkipResponse:
        if not request.actor_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "actor_id is required")
        if not request.target_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "target_id is required")

        _ = await self._handle_skip.execute(
            HandleSkip.Request(
                actor_telegram_id=request.actor_id,
                target_telegram_id=request.target_id,
            )
        )
        return match_pb2.HandleSkipResponse(success=True)
