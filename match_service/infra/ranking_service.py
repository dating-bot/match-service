from collections.abc import AsyncGenerator

import grpclib.client
from pydantic import BaseModel, Field

from external_clients.ranking_api.v1.ranking_grpc import RankingServiceStub


class RankingServiceConfig(BaseModel):
    host: str = Field(description="ranking-service gRPC host")
    port: int = Field(default=50053, description="ranking-service gRPC port")


async def provide_ranking_stub(config: RankingServiceConfig) -> AsyncGenerator[RankingServiceStub]:
    channel = grpclib.client.Channel(host=config.host, port=config.port)
    try:
        yield RankingServiceStub(channel)
    finally:
        channel.close()
