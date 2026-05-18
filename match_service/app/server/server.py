import asyncio
import signal

import grpclib.server
import structlog

from match_service import infra
from match_service.app.consumers.interaction_consumer import InteractionConsumer
from match_service.app.server import di
from match_service.app.server.grpc_handler import MatchServiceHandler
from match_service.app.server.utils.logger import configure_logger
from match_service.infra.tracing import setup_tracing

log = structlog.stdlib.get_logger("match_service.server")


async def run_grpc_server(
    handler: MatchServiceHandler,
    config: infra.GrpcServerConfig,
) -> None:
    server = grpclib.server.Server([handler])
    await server.start(config.host, config.port)
    log.info("gRPC server started", host=config.host, port=config.port)

    try:
        await server.wait_closed()
    except asyncio.CancelledError:
        log.info("gRPC server cancelled, shutting down")
        server.close()
        await server.wait_closed()


async def main() -> None:
    config = await di.container.get(infra.GlobalConfig)

    configure_logger(
        json_mode=False,
        log_level="DEBUG" if config.debug else "INFO",
    )
    setup_tracing(service_name="match-service")
    log.info("Starting match-service")

    consumer = await di.container.get(InteractionConsumer)
    grpc_handler_instance = await di.container.get(MatchServiceHandler)
    grpc_config = await di.container.get(infra.GrpcServerConfig)

    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        log.info("Shutdown signal received, stopping server")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    consumer_task = asyncio.create_task(consumer.run())
    log.info("Consumer started", queues=["interaction.like", "interaction.skip"])

    grpc_task = asyncio.create_task(run_grpc_server(grpc_handler_instance, grpc_config))
    log.info("gRPC server task started")

    try:
        _ = await shutdown_event.wait()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        log.info("Stopping server")
        _ = consumer_task.cancel()
        _ = grpc_task.cancel()
        _ = await asyncio.gather(consumer_task, grpc_task, return_exceptions=True)
        await di.container.close()
        log.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
