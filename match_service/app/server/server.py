import asyncio
import signal

import structlog

from match_service import infra
from match_service.app.consumers.interaction_consumer import InteractionConsumer
from match_service.app.server import di
from match_service.app.server.utils.logger import configure_logger

log = structlog.stdlib.get_logger("match_service.server")


async def main() -> None:
    config = await di.container.get(infra.GlobalConfig)

    configure_logger(
        json_mode=False,
        log_level="DEBUG" if config.debug else "INFO",
    )
    log.info("Starting match-service")

    consumer = await di.container.get(InteractionConsumer)

    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        log.info("Shutdown signal received, stopping server")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    consumer_task = asyncio.create_task(consumer.run())
    log.info("Consumer started", queues=["interaction.like", "interaction.skip"])

    try:
        _ = await shutdown_event.wait()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        log.info("Stopping server")
        consumer_task.cancel()
        _ = await asyncio.gather(consumer_task, return_exceptions=True)
        await di.container.close()
        log.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
