from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar, cast

import grpclib.exceptions
import structlog
from grpclib.const import Status as GRPCStatus

log = structlog.stdlib.get_logger("match_service.utils.grpc_error_handler")

P = ParamSpec("P")
R = TypeVar("R", bound=Awaitable[None])


def handle_grpc_errors(
    *error_mappings: tuple[type[Exception], GRPCStatus],
    default_status: GRPCStatus = GRPCStatus.INTERNAL,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for handling errors in gRPC handlers.

    Converts usecase exceptions to appropriate gRPC statuses.

    Args:
        *error_mappings: Tuples of (ExceptionType, GRPCStatus) for error mapping
        default_status: Default status for unhandled errors

    """

    def decorator(handler: Callable[P, R]) -> Callable[P, R]:
        @wraps(handler)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            try:
                await handler(*args, **kwargs)
            except Exception as e:
                for error_type, grpc_status in error_mappings:
                    if isinstance(e, error_type):
                        log.warning("error in grpc handler", error_type=error_type.__name__, error=str(e))
                        raise grpclib.exceptions.GRPCError(grpc_status, str(e)) from e

                log.exception("unexpected error in grpc handler", error=str(e), err=e)
                raise grpclib.exceptions.GRPCError(default_status, "Internal server error") from e

        return cast("Callable[P, R]", wrapper)

    return decorator
