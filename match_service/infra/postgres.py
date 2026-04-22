from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class PostgresConfig(BaseModel):
    host: str = Field(description="Хост")
    port: int = Field(description="Порт")
    username: str = Field(description="Имя пользователя")
    password: str = Field(description="Пароль пользователя")
    database: str = Field(description="Имя базы данных")

    should_log_sql: bool | None = Field(
        default=False,
        description="Включить ли логирование SQL-запросов.",
    )
    pool_size: int = Field(default=10, description="Максимальное количество соединений в пуле")
    pool_max_overflow: int | None = Field(
        default=20,
        description="Максимальное количество соединений сверх лимита пула.",
    )

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class AsyncSessionFactory(async_sessionmaker[AsyncSession]): ...


async def provide_async_engine(config: PostgresConfig) -> AsyncGenerator[AsyncEngine]:
    kw: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
        "pool_size": config.pool_size,
    }
    if config.should_log_sql is not None:
        kw["echo"] = config.should_log_sql
    if config.pool_max_overflow is not None:
        kw["max_overflow"] = config.pool_max_overflow

    engine = create_async_engine(config.url, **kw)
    try:
        yield engine
    finally:
        await engine.dispose()


async def provide_async_session_factory(engine: AsyncEngine) -> AsyncSessionFactory:
    return AsyncSessionFactory(engine, class_=AsyncSession, expire_on_commit=False)
