import os
import subprocess

import pytest
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

from app.shared.database import dispose_engine, init_engine


@pytest.fixture(scope="session", autouse=True)
async def postgres():
    with PostgresContainer("postgres:16") as postgres:

        database_url = (
            postgres.get_connection_url()
            .replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            .replace("postgresql://", "postgresql+asyncpg://")
        )

        # Run migrations as admin
        subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            env={
                **os.environ,
                "DATABASE_URL": database_url,
            },
        )

        # Create application user
        sync_url = database_url.replace(
            "postgresql+asyncpg://",
            "postgresql+psycopg://",
        )

        engine = create_engine(sync_url)

        with engine.begin() as conn:
            conn.execute(text("""
                CREATE ROLE app_user
                LOGIN
                PASSWORD 'password'
                NOSUPERUSER
                NOBYPASSRLS;
            """))

            conn.execute(text("""
                GRANT USAGE ON SCHEMA public TO app_user;

                GRANT SELECT, INSERT, UPDATE, DELETE
                ON ALL TABLES IN SCHEMA public
                TO app_user;

                GRANT USAGE, SELECT
                ON ALL SEQUENCES IN SCHEMA public
                TO app_user;
            """))

        engine.dispose()

        app_database_url = database_url.replace(
            "test:test@",
            "app_user:password@",
        )

        init_engine(app_database_url)

        yield

        await dispose_engine()