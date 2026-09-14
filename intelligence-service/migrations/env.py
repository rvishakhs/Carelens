"""Independent intelligence database migrations; never reads CareLens DATABASE_URL."""

import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
url = os.getenv("INTELLIGENCE_MIGRATION_DATABASE_URL")

if context.is_offline_mode():
    context.configure(url="postgresql+psycopg://", literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    if not url:
        raise RuntimeError("Set INTELLIGENCE_MIGRATION_DATABASE_URL for the intelligence database")
    engine = create_engine(url, poolclass=pool.NullPool)
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Intelligence migrations require PostgreSQL")
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
