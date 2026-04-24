import asyncio
from datetime import UTC, datetime

import structlog
from celery import shared_task
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from match_service.infra.config import GlobalConfig
from match_service.infra.valkey import ValkeyClient

log = structlog.stdlib.get_logger("match_service.tasks.flush_match_activity")


async def _flush_match_activity() -> int:
    config = GlobalConfig.load()
    engine = create_async_engine(config.postgres.url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    valkey = ValkeyClient(config.valkey)
    _ = await valkey.initialize()

    flushed = 0

    try:
        keys = await valkey.client.keys("match_activity:*")
        log.debug("found match_activity keys", count=len(keys))

        for key in keys:
            match_id = key.split(":")[1]
            ts = await valkey.client.get(key)
            if ts:
                try:
                    parsed_ts = datetime.fromisoformat(ts)
                    if parsed_ts.tzinfo is None:
                        parsed_ts = parsed_ts.replace(tzinfo=UTC)
                except ValueError:
                    log.warning("invalid match activity timestamp in valkey, using current time", key=key, raw_value=ts)
                    parsed_ts = datetime.now(UTC)

                async with session_factory() as session:
                    _ = await session.execute(
                        text("""
                            UPDATE matches
                            SET match_last_activity = :ts
                            WHERE id = :match_id
                        """),
                        {"ts": parsed_ts, "match_id": int(match_id)},
                    )
                    await session.commit()
                await valkey.client.delete(key)
                flushed += 1
                log.debug("flushed match activity", match_id=match_id)

        log.info("flush_match_activity completed", flushed=flushed)
        return flushed
    finally:
        await valkey.close()
        await engine.dispose()


@shared_task
def flush_match_activity() -> dict[str, int]:
    flushed = asyncio.run(_flush_match_activity())
    return {"flushed": flushed}
