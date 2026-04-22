import uuid
from datetime import UTC, datetime
from enum import StrEnum

import pydantic


class OutboxEventStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class OutboxEvent(pydantic.BaseModel):
    id: uuid.UUID = pydantic.Field(description="Event ID")
    event_type: str = pydantic.Field(description="Event type identifier")
    payload: dict[str, object] = pydantic.Field(description="Event payload")
    status: OutboxEventStatus = pydantic.Field(description="Processing status")
    attempts: int = pydantic.Field(default=0, description="Number of publish attempts")
    created_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation timestamp",
    )
    updated_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Last status update timestamp",
    )
