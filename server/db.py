"""Async DB setup. Postgres in production (same instance as the LangGraph
checkpointer); SQLite fallback for local dev and offline tests."""

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DEV_URL = "sqlite+aiosqlite:///./blindspot.db"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", DEFAULT_DEV_URL)
    # Normalize plain postgres URLs to the psycopg async driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def is_postgres(url: str | None = None) -> bool:
    return (url or database_url()).startswith("postgresql")


def make_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(url or database_url())


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
