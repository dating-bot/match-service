from typing import final

import dishka
from sqlalchemy.ext.asyncio import AsyncSession

from external_clients.ranking_api.v1.ranking_grpc import RankingServiceStub
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
    ranking_stub = dishka.provide(staticmethod(infra.provide_ranking_stub), provides=RankingServiceStub)


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

    @dishka.provide
    def provide_list_user_matches(
        self,
        match_repo: protocols.MatchRepositoryProtocol[AsyncSession],
    ) -> usecases.ListUserMatches[AsyncSession]:
        """юзкейс списка мэтчей пользователя (отладка / UI)"""
        return usecases.ListUserMatches[AsyncSession](match_repository=match_repo)


@final
class AppProvider(dishka.Provider):
    scope = dishka.Scope.APP

    @dishka.provide
    def provide_interaction_consumer(
        self,
        topology: infra.MatchServiceTopology,
        handle_like: usecases.HandleLike[AsyncSession],
        handle_skip: usecases.HandleSkip[AsyncSession],
        ranking_stub: RankingServiceStub,
    ) -> InteractionConsumer:
        return InteractionConsumer(
            topology=topology,
            handle_like=handle_like,
            handle_skip=handle_skip,
            ranking_stub=ranking_stub,
        )

    @dishka.provide
    def provide_match_service_handler(
        self,
        handle_like: usecases.HandleLike[AsyncSession],
        handle_skip: usecases.HandleSkip[AsyncSession],
        list_user_matches: usecases.ListUserMatches[AsyncSession],
    ) -> grpc_handler.MatchServiceHandler:
        return grpc_handler.MatchServiceHandler(
            _handle_like=handle_like,
            _handle_skip=handle_skip,
            _list_user_matches=list_user_matches,
        )


container = dishka.make_async_container(InfraProvider(), AdapterProvider(), UsecaseProvider(), AppProvider())
