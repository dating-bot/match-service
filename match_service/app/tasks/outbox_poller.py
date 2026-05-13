import asyncio
import json
from typing import final

import aio_pika
import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from match_service.adapters.outbox import PostgresOutboxRepositoryAdapter
from match_service.infra.config import GlobalConfig
from match_service.infra.rabbitmq_connection import RabbitMQConfig

log = structlog.stdlib.get_logger("match_service.tasks.outbox_poller")

MATCH_CREATED_EXCHANGE = "match.events"
MATCH_CREATED_ROUTING_KEY = "match.created"


@final
class OutboxPublisher:
    def __init__(self, config: RabbitMQConfig) -> None:
        self._config = config

    async def publish(self, event_type: str, payload: dict[str, object]) -> None:
        connection = await aio_pika.connect_robust(self._config.dsn)
        try:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                MATCH_CREATED_EXCHANGE,
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )
            trace_id = str(payload.get("trace_id") or "")
            headers = {"trace_id": trace_id} if trace_id else None
            message = aio_pika.Message(
                body=json.dumps(payload).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers=headers,
            )
            _ = await exchange.publish(message, routing_key=event_type)
            log.debug("published outbox event", event_type=event_type, payload=payload)
        finally:
            await connection.close()


async def _process_outbox_events() -> int:
    config = GlobalConfig.load()
    engine = create_async_engine(config.postgres.url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    outbox_repo = PostgresOutboxRepositoryAdapter(session_factory=session_factory)
    publisher = OutboxPublisher(config.rabbitmq)

    processed_count = 0

    try:
        async with outbox_repo.context() as session:
            pending_events = await outbox_repo.get_pending_events(session, limit=100)

            for event in pending_events:
                await outbox_repo.mark_running(session, event.id)
                try:
                    await publisher.publish(event.event_type, event.payload)
                    await outbox_repo.mark_done(session, event.id)
                    processed_count += 1
                    log.info(
                        "outbox event processed",
                        event_id=event.id,
                        event_type=event.event_type,
                    )
                except Exception as e:
                    log.exception(
                        "failed to publish outbox event",
                        event_id=event.id,
                        event_type=event.event_type,
                        err=e,
                    )
                    await outbox_repo.mark_failed(session, event.id)
    finally:
        await engine.dispose()

    return processed_count


@shared_task
def outbox_poller() -> dict[str, int]:
    processed = asyncio.run(_process_outbox_events())
    log.info("outbox_poller completed", processed_count=processed)
    return {"processed": processed}
