from collections.abc import AsyncGenerator
from dataclasses import dataclass

import aio_pika
from aio_pika import ExchangeType

INTERACTION_DLX = "interaction.dlx"
INTERACTION_DEAD_QUEUE = "interaction.dead"
INTERACTION_LIKE_QUEUE = "interaction.like"
INTERACTION_SKIP_QUEUE = "interaction.skip"

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


async def provide_match_service_topology(
    connection: aio_pika.abc.AbstractRobustConnection,
) -> AsyncGenerator[MatchServiceTopology]:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    dlx = await channel.declare_exchange(INTERACTION_DLX, ExchangeType.DIRECT, durable=True)

    dead_queue = await channel.declare_queue(INTERACTION_DEAD_QUEUE, durable=True)
    await dead_queue.bind(dlx, routing_key=INTERACTION_DEAD_QUEUE)

    like_queue = await channel.declare_queue(
        INTERACTION_LIKE_QUEUE,
        durable=True,
        arguments=_QUORUM_ARGS,
    )
    skip_queue = await channel.declare_queue(
        INTERACTION_SKIP_QUEUE,
        durable=True,
        arguments=_QUORUM_ARGS,
    )

    try:
        yield MatchServiceTopology(like_queue=like_queue, skip_queue=skip_queue, channel=channel)
    finally:
        if not channel.is_closed:
            await channel.close()
