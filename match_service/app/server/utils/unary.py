from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog.stdlib
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from grpclib.server import Stream

type UnaryHandler[T, I: Message, O: Message] = Callable[[T, I], Awaitable[O]]

log = structlog.stdlib.get_logger("match_service.grpc.handler")


def unary[T, I: Message, O: Message](handler: UnaryHandler[T, I, O]):
    async def wrapper(self: T, stream: Stream[I, O]) -> None:
        trace_id = _extract_trace_id(stream) or uuid4().hex
        with structlog.contextvars.bound_contextvars(trace_id=trace_id):
            request = await stream.recv_message()
            if request is None:
                log.warning("received None (no request), skipping handlers", handler=wrapper.__qualname__)
                return

            log.debug(
                "grpc handler invoked",
                handler=wrapper.__qualname__,
                request=MessageToDict(request, preserving_proto_field_name=True),
            )

            response = await handler(self, request)

            log.debug(
                "grpc handler response",
                handler=wrapper.__qualname__,
                response=MessageToDict(response, preserving_proto_field_name=True),
            )

            await stream.send_message(response)

    wrapper.__qualname__ = handler.__qualname__
    wrapper.__name__ = handler.__name__
    wrapper.__doc__ = handler.__doc__

    return wrapper


def _extract_trace_id(stream: Stream[Message, Message]) -> str | None:
    metadata = getattr(stream, "metadata", None)
    if metadata is None:
        return None
    trace_id = metadata.get("trace_id")
    if trace_id:
        return str(trace_id)
    traceparent = metadata.get("traceparent")
    if traceparent:
        return str(traceparent)
    return None
