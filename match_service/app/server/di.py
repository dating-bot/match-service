from typing import final

import dishka
from sqlalchemy.ext.asyncio import AsyncSession

from match_service import adapters, infra, protocols, usecases
from match_service.app.consumers.interaction_consumer import InteractionConsumer
from match_service.app.server import grpc_handler


@final
class InfraProvider(dishka.Provider):
    scope = dishka.Scope.APP

    global_config = dishka.provide(staticmethod(infra.GlobalConfig.load))
    subconfigs = dishka.provide_all(*infra.GlobalConfig.subconfigs())
    async_engine = dishka.provide(staticmethod(infra.provide_async_engine))
    async_session_factory = dishka.provide(staticmethod(infra.provide_async_session_factory))
    rabbitmq_connection = dishka.provide(staticmethod(infra.provide_rabbitmq_connection))
    topology = dishka.provide(staticmethod(infra.provide_match_service_topology))
    valkey = dishka.provide(staticmethod(infra.provide_valkey_client))


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
    interaction_staging_repository = dishka.provide(
        source=adapters.PostgresInteractionStagingRepositoryAdapter,
        provides=protocols.InteractionStagingRepositoryProtocol,
    )


@final
class UsecaseProvider(dishka.Provider):
    scope = dishka.Scope.APP

    @dishka.provide
    def provide_handle_like(
        self,
        like_repo: protocols.LikeRepositoryProtocol[AsyncSession],
        match_repo: protocols.MatchRepositoryProtocol[AsyncSession],
        outbox_repo: protocols.OutboxRepositoryProtocol[AsyncSession],
        valkey: infra.ValkeyClient,
        valkey_config: infra.ValkeyConfig,
    ) -> usecases.HandleLike[AsyncSession]:
        """юзкейс обработки лайка с созданием матча и outbox-события"""
        return usecases.HandleLike[AsyncSession](
            like_repository=like_repo,
            match_repository=match_repo,
            outbox_repository=outbox_repo,
            valkey=valkey,
            match_debounce_ttl=valkey_config.match_debounce_ttl_seconds,
        )

    @dishka.provide
    def provide_handle_skip(
        self,
        staging_repo: protocols.InteractionStagingRepositoryProtocol[AsyncSession],
    ) -> usecases.HandleSkip[AsyncSession]:
        """юзкейс обработки скипа"""
        return usecases.HandleSkip[AsyncSession](interaction_staging_repository=staging_repo)


@final
class AppProvider(dishka.Provider):
    scope = dishka.Scope.APP

    interaction_consumer = dishka.provide(InteractionConsumer)
    grpc_handler = dishka.provide(grpc_handler.MatchServiceHandler)


container = dishka.make_async_container(InfraProvider(), AdapterProvider(), UsecaseProvider(), AppProvider())
