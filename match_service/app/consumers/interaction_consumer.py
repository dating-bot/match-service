import asyncio
import json
from typing import final

import aio_pika.abc
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from match_service.domain.like import LikeStatus
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
    ) -> None:
        self._topology = topology
        self._handle_like = handle_like
        self._handle_skip = handle_skip

    async def run(self) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._consume_likes())
            tg.create_task(self._consume_skips())

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
        liker = int(data["liker_telegram_id"])  # type: ignore[arg-type]
        liked = int(data["liked_telegram_id"])  # type: ignore[arg-type]
        status = LikeStatus(str(data.get("status", LikeStatus.LIKED)))

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
        except HandleLikeDuplicateError:
            log.warning("duplicate like ignored", liker=liker, liked=liked)

    async def _on_skip(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        data: dict[str, object] = json.loads(message.body)
        actor = int(data["actor_telegram_id"])  # type: ignore[arg-type]
        target = int(data["target_telegram_id"])  # type: ignore[arg-type]

        await self._handle_skip.execute(HandleSkip.Request(actor_telegram_id=actor, target_telegram_id=target))
        log.debug("skip processed", actor=actor, target=target)
