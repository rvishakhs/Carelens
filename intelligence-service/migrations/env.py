"""Independent intelligence database migrations; never reads CareLens DATABASE_URL."""

import os
from pathlib import Path
import asyncio
import logging

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool, Connection, text
from sqlalchemy.ext.asyncio import create_async_engine
from intelligence.config import Settings
from intelligence.persistence.database import Base
from intelligence.persistence import models  # noqa: F401

# load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
# url = os.getenv("INTELLIGENCE_MIGRATION_DATABASE_URL")
#
# if context.is_offline_mode():
#     context.configure(url="postgresql+psycopg://", literal_binds=True, dialect_opts={"paramstyle": "named"})
#     with context.begin_transaction():
#         context.run_migrations()
# else:
#     if not url:
#         raise RuntimeError("Set INTELLIGENCE_MIGRATION_DATABASE_URL for the intelligence database")
#     engine = create_engine(url, poolclass=pool.NullPool)
#     if engine.dialect.name != "postgresql":
#         raise RuntimeError("Intelligence migrations require PostgreSQL")
#     with engine.connect() as connection:
#         context.configure(connection=connection)
#         with context.begin_transaction():
#             context.run_migrations()
#     engine.dispose()



config = context.config

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

settings = Settings()
database_url = settings.database_url.get_secret_value()

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
            result = await connection.execute(
                text("""
                    SELECT
                        current_database() AS database_name,
                        current_user AS connected_user,
                        session_user AS login_user
                """)
            )

            print(
                "Alembic connection:",
                dict(result.mappings().one()),
                flush=True,
            )

            await connection.rollback()

            await connection.run_sync(do_run_migrations)

    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())