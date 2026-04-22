from dataclasses import dataclass
from typing import final

import structlog

from match_service.domain.interaction import InteractionStaging
from match_service.protocols.interaction_staging.repository import InteractionStagingRepositoryProtocol

log = structlog.stdlib.get_logger("match_service.usecases.HandleSkip")


@final
class HandleSkip[SessionT]:
    def __init__(
        self,
        *,
        interaction_staging_repository: InteractionStagingRepositoryProtocol[SessionT],
    ) -> None:
        self._staging_repository = interaction_staging_repository

    @dataclass
    class Request:
        actor_telegram_id: int
        target_telegram_id: int

    @dataclass
    class Response:
        staging: InteractionStaging

    async def execute(self, request: Request) -> Response:
        async with self._staging_repository.context() as session:
            staging = await self._staging_repository.insert_staging(
                session,
                InteractionStagingRepositoryProtocol.InsertStagingRequest(
                    actor_telegram_id=request.actor_telegram_id,
                    target_telegram_id=request.target_telegram_id,
                ),
            )
        log.debug(
            "skip handled",
            actor=request.actor_telegram_id,
            target=request.target_telegram_id,
        )
        return self.Response(staging=staging)
