import asyncio
import signal

import structlog

from match_service import infra
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

    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        log.info("Shutdown signal received, stopping server")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    log.info("Server started successfully")

    try:
        _ = await shutdown_event.wait()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        log.info("Stopping server")
        await di.container.close()
        log.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
