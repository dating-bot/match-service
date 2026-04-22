from collections.abc import AsyncGenerator
from dataclasses import dataclass

import aio_pika
from aio_pika import ExchangeType

INTERACTION_DLX = "interaction.dlx"
INTERACTION_DEAD_QUEUE = "interaction.dead"
INTERACTION_LIKE_QUEUE = "interaction.like"
INTERACTION_SKIP_QUEUE = "interaction.skip"
RANKING_ENGAGEMENT_QUEUE = "ranking.engagement"
RANKING_ENGAGEMENT_EXCHANGE = "ranking.engagement"

_QUORUM_ARGS: dict[str, object] = {
    "x-queue-type": "quorum",
    "x-delivery-limit": 3,
    "x-dead-letter-exchange": INTERACTION_DLX,
}


@dataclass(slots=True)
class MatchServiceTopology:
    like_queue: aio_pika.abc.AbstractQueue
    skip_queue: aio_pika.abc.AbstractQueue
    channel: aio_pika.abc.AbstractChannel
    ranking_engagement_exchange: aio_pika.abc.AbstractExchange


async def provide_match_service_topology(
    connection: aio_pika.abc.AbstractRobustConnection,
) -> AsyncGenerator[MatchServiceTopology]:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    dlx = await channel.declare_exchange(INTERACTION_DLX, ExchangeType.DIRECT, durable=True)

    dead_queue = await channel.declare_queue(INTERACTION_DEAD_QUEUE, durable=True)
    await dead_queue.bind(dlx, routing_key=INTERACTION_DEAD_QUEUE)

    like_queue = await channel.declare_queue(
        name=INTERACTION_LIKE_QUEUE,
        durable=True,
        arguments=_QUORUM_ARGS,
    )
    skip_queue = await channel.declare_queue(
        name=INTERACTION_SKIP_QUEUE,
        durable=True,
        arguments=_QUORUM_ARGS,
    )

    ranking_exchange = await channel.declare_exchange(
        RANKING_ENGAGEMENT_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )
    ranking_queue = await channel.declare_queue(
        RANKING_ENGAGEMENT_QUEUE,
        durable=True,
    )
    await ranking_queue.bind(ranking_exchange, routing_key=RANKING_ENGAGEMENT_QUEUE)

    try:
        yield MatchServiceTopology(
            like_queue=like_queue,
            skip_queue=skip_queue,
            channel=channel,
            ranking_engagement_exchange=ranking_exchange,
        )
    finally:
        if not channel.is_closed:
            await channel.close()
