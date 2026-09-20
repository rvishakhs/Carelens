"""Migrations use dedicated credentials, independently of API settings."""

import asyncio
import logging

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from intelligence.config import MigrationSettings
from intelligence.persistence import models  # noqa: F401
from intelligence.persistence.database import Base

config = context.config

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

settings = MigrationSettings()
database_url = settings.migration_database_url.get_secret_value()

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to PostgreSQL."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migration operations using the supplied connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
        hide_parameters=True,
    )

    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)

    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
