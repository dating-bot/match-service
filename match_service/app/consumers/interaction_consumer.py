import asyncio
import json
from typing import final

import aio_pika.abc
import structlog
import structlog.contextvars
from sqlalchemy.ext.asyncio import AsyncSession

from external_clients.ranking_api.v1.ranking_pb2 import UpdateEngagementRequest
from match_service.domain.like import LikeStatus
from match_service.infra.tracing import attach_context_from_headers, current_trace_id, inject_grpc_metadata
from match_service.infra.rabbitmq_topology import MatchServiceTopology
from match_service.usecases.handle_like.usecase import HandleLike, HandleLikeDuplicateError
from match_service.usecases.handle_skip.usecase import HandleSkip

log = structlog.stdlib.get_logger("match_service.consumers.InteractionConsumer")


@final
class InteractionConsumer:
    def __init__(
        self,
        *,
        topology: MatchServiceTopology,
        handle_like: HandleLike[AsyncSession],
        handle_skip: HandleSkip[AsyncSession],
        ranking_stub,
    ) -> None:
        self._topology = topology
        self._handle_like = handle_like
        self._handle_skip = handle_skip
        self._ranking_stub = ranking_stub

    async def run(self) -> None:
        async with asyncio.TaskGroup() as tg:
            _ = tg.create_task(self._consume_likes())
            _ = tg.create_task(self._consume_skips())

    async def _consume_likes(self) -> None:
        async with self._topology.like_queue.iterator() as it:
            async for message in it:
                async with message.process(ignore_processed=True):
                    await self._on_like(message)

    async def _consume_skips(self) -> None:
        async with self._topology.skip_queue.iterator() as it:
            async for message in it:
                async with message.process(ignore_processed=True):
                    await self._on_skip(message)

    async def _on_like(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        data: dict[str, object] = json.loads(message.body)
        with attach_context_from_headers(message.headers):
            trace_id = _extract_trace_id(message.headers) or current_trace_id() or "mq-no-trace"
            liker = int(data["liker_telegram_id"])  # type: ignore[arg-type]
            liked = int(data["liked_telegram_id"])  # type: ignore[arg-type]
            status = LikeStatus(str(data.get("status", LikeStatus.LIKED)))

            with structlog.contextvars.bound_contextvars(trace_id=trace_id):
                try:
                    result = await self._handle_like.execute(
                        HandleLike.Request(
                            liker_telegram_id=liker,
                            liked_telegram_id=liked,
                            status=status,
                        )
                    )
                    log.info(
                        "like processed",
                        liker=liker,
                        liked=liked,
                        is_new_match=result.is_new_match,
                    )
                    if result.is_new_match and result.match is not None:
                        await self._notify_ranking_service(
                            user1=result.match.user1_telegram_id,
                            user2=result.match.user2_telegram_id,
                            event_type="match_created",
                            trace_id=trace_id,
                        )
                except HandleLikeDuplicateError:
                    log.warning("duplicate like ignored", liker=liker, liked=liked)

    async def _notify_ranking_service(
        self,
        user1: int,
        user2: int,
        event_type: str,
        trace_id: str,
    ) -> None:
        try:
            metadata = inject_grpc_metadata([("trace_id", trace_id)] if trace_id else None)
            await self._ranking_stub.UpdateEngagement(
                UpdateEngagementRequest(
                    user1_telegram_id=user1,
                    user2_telegram_id=user2,
                    event_type=event_type,
                ),
                metadata=metadata,
            )
            log.debug("ranking_service notified", user1=user1, user2=user2, event_type=event_type)
        except Exception:
            log.exception("failed to notify ranking_service", user1=user1, user2=user2)

    async def _on_skip(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        data: dict[str, object] = json.loads(message.body)
        with attach_context_from_headers(message.headers):
            trace_id = _extract_trace_id(message.headers) or current_trace_id() or "mq-no-trace"
            actor = int(data["actor_telegram_id"])  # type: ignore[arg-type]
            target = int(data["target_telegram_id"])  # type: ignore[arg-type]

            with structlog.contextvars.bound_contextvars(trace_id=trace_id):
                _ = await self._handle_skip.execute(
                    HandleSkip.Request(actor_telegram_id=actor, target_telegram_id=target)
                )
                log.debug("skip processed", actor=actor, target=target)


def _extract_trace_id(headers: dict[str, object] | None) -> str:
    if not headers:
        return "mq-no-trace"
    trace_id = headers.get("trace_id")
    if isinstance(trace_id, bytes):
        return trace_id.decode("utf-8", errors="ignore")
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    traceparent = headers.get("traceparent")
    if isinstance(traceparent, bytes):
        traceparent = traceparent.decode("utf-8", errors="ignore")
    if isinstance(traceparent, str) and traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 4 and len(parts[1]) == 32:
            return parts[1]
        return traceparent
    return "mq-no-trace"
