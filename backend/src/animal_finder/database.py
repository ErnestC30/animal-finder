import contextlib
from pydantic import PostgresDsn
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    AsyncConnection,
    async_sessionmaker,
    create_async_engine,
)


from animal_finder.config import DbSettings


async def get_db():
    async with sessionmanager.session() as session:
        yield session


settings = DbSettings()
db_url = PostgresDsn.build(
    scheme="postgresql+asyncpg",
    host=settings.db_host,
    username=settings.db_user,
    password=settings.db_password.get_secret_value(),
    path=settings.db_name,
).unicode_string()


class DatabaseSessionManager:
    def __init__(self, db_url: str) -> None:
        self._async_engine: AsyncEngine | None = None
        self._async_sessionmaker: async_sessionmaker[AsyncSession] | None = None
        self.db_url = db_url

    def init(self) -> None:
        # should configure async engine settings
        # add 'echo=True' parameter to view raw SQL
        self._async_engine = create_async_engine(
            self.db_url,
            pool_pre_ping=True,
            pool_timeout=30,
            pool_recycle=1800,
        )
        self._async_sessionmaker = async_sessionmaker(
            bind=self._async_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    async def close(self) -> None:
        if self._async_engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        await self._async_engine.dispose()
        self._async_engine = None
        self._async_sessionmaker = None

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._async_sessionmaker is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")

        session = self._async_sessionmaker()
        try:
            yield session
        finally:
            await session.close()

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncConnection, None]:
        """
        Async context manager for raw database connections
        """
        if self._async_engine is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")

        async with self._async_engine.begin() as connection:
            yield connection


sessionmanager = DatabaseSessionManager(db_url)

# Use sync database for handling celery tasks
# sync_db_url = PostgresDsn.build(
#     scheme="postgresql+psycopg2",
#     host=settings.db_host,
#     username=settings.db_user,
#     password=settings.db_password,
#     path=settings.db_name,
# ).unicode_string()

# sync_engine = create_engine(sync_db_url)
