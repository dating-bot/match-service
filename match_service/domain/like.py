from datetime import UTC, datetime
from enum import StrEnum

import pydantic


class LikeStatus(StrEnum):
    LIKED = "liked"
    PASSED = "passed"
    SUPERLIKED = "superliked"


class Like(pydantic.BaseModel):
    id: int = pydantic.Field(description="Like ID")
    liker_telegram_id: int = pydantic.Field(description="Telegram ID of the user who liked")
    liked_telegram_id: int = pydantic.Field(description="Telegram ID of the user who was liked")
    status: LikeStatus = pydantic.Field(description="Like status")
    created_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation timestamp",
    )
