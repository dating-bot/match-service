from typing import final

import dishka
from sqlalchemy.ext.asyncio import AsyncSession

from match_service import adapters, infra, protocols


@final
class InfraProvider(dishka.Provider):
    scope = dishka.Scope.APP

    global_config = dishka.provide(staticmethod(infra.GlobalConfig.load))
    subconfigs = dishka.provide_all(*infra.GlobalConfig.subconfigs())
    async_engine = dishka.provide(staticmethod(infra.provide_async_engine))
    async_session_factory = dishka.provide(staticmethod(infra.provide_async_session_factory))
    rabbitmq_connection = dishka.provide(staticmethod(infra.provide_rabbitmq_connection))


@final
class AdapterProvider(dishka.Provider):
    scope = dishka.Scope.APP

    like_repository = dishka.provide(
        source=adapters.PostgresLikeRepositoryAdapter,
        provides=protocols.LikeRepositoryProtocol,
    )
    match_repository = dishka.provide(
        source=adapters.PostgresMatchRepositoryAdapter,
        provides=protocols.MatchRepositoryProtocol,
    )
    outbox_repository = dishka.provide(
        source=adapters.PostgresOutboxRepositoryAdapter,
        provides=protocols.OutboxRepositoryProtocol,
    )


@final
class UsecaseProvider(dishka.Provider):
    scope = dishka.Scope.APP


container = dishka.make_async_container(InfraProvider(), AdapterProvider(), UsecaseProvider())
