from datetime import UTC, datetime

import pydantic


class InteractionStaging(pydantic.BaseModel):
    id: int = pydantic.Field(description="Staging record ID")
    actor_telegram_id: int = pydantic.Field(description="Telegram ID of the user who skipped")
    target_telegram_id: int = pydantic.Field(description="Telegram ID of the skipped user")
    created_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation timestamp",
    )
