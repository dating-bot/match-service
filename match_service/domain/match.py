from datetime import UTC, datetime
from enum import StrEnum

import pydantic


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class Match(pydantic.BaseModel):
    id: int = pydantic.Field(description="Match ID")
    user1_telegram_id: int = pydantic.Field(description="Telegram ID of first user (smaller ID)")
    user2_telegram_id: int = pydantic.Field(description="Telegram ID of second user (larger ID)")
    created_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation timestamp",
    )


class Conversation(pydantic.BaseModel):
    id: int = pydantic.Field(description="Conversation ID")
    match_id: int = pydantic.Field(description="FK to matches.id")
    status: ConversationStatus = pydantic.Field(description="Conversation status")
    created_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation timestamp",
    )
