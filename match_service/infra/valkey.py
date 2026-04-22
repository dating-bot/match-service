from collections.abc import AsyncGenerator

import redis.asyncio as redis
from pydantic import BaseModel, Field

ValkeyClient = redis.Redis


class ValkeyConfig(BaseModel):
    host: str = Field(description="Хост")
    port: int = Field(default=6379, description="Порт")
    db: int = Field(default=0, description="Номер базы данных")
    password: str | None = Field(default=None, description="Пароль")
    match_debounce_ttl_seconds: int = Field(
        default=300,
        description="TTL ключа дебаунса match_activity (секунды)",
    )


async def provide_valkey_client(config: ValkeyConfig) -> AsyncGenerator[ValkeyClient]:
    client: ValkeyClient = redis.Redis(
        host=config.host,
        port=config.port,
        db=config.db,
        password=config.password,
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()
