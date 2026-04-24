import asyncio

import structlog
from celery import shared_task
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from match_service.infra.config import GlobalConfig

log = structlog.stdlib.get_logger("match_service.tasks.check_ghosted_matches")


async def _check_ghosted_matches() -> dict[str, int]:
    config = GlobalConfig.load()
    engine = create_async_engine(config.postgres.url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    warnings_sent = 0
    stale_marked = 0

    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""
                    UPDATE matches
                    SET ghost_warning_sent = TRUE
                    WHERE id IN (
                        SELECT id FROM matches
                        WHERE match_last_activity < NOW() - INTERVAL '3 days'
                        AND is_stale = FALSE
                        AND ghost_warning_sent = FALSE
                    )
                    RETURNING id
                """)
            )
            warned_matches = result.fetchall()
            await session.commit()
            warnings_sent = len(warned_matches)

            for row in warned_matches:
                log.info("ghost warning sent", match_id=row[0])

        async with session_factory() as session:
            result = await session.execute(
                text("""
                    UPDATE matches
                    SET is_stale = TRUE
                    WHERE id IN (
                        SELECT id FROM matches
                        WHERE match_last_activity < NOW() - INTERVAL '7 days'
                        AND is_stale = FALSE
                    )
                    RETURNING id
                """)
            )
            stale_matches = result.fetchall()
            await session.commit()
            stale_marked = len(stale_matches)

            for row in stale_matches:
                log.info("match marked stale", match_id=row[0])

        log.info(
            "check_ghosted_matches completed",
            warnings_sent=warnings_sent,
            stale_marked=stale_marked,
        )
        return {"warnings_sent": warnings_sent, "stale_marked": stale_marked}
    finally:
        await engine.dispose()


@shared_task
def check_ghosted_matches() -> dict[str, int]:
    return asyncio.run(_check_ghosted_matches())
