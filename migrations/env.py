import os
from logging.config import fileConfig
from app.config import get_settings

settings = get_settings()

from sqlalchemy import engine_from_config, pool

from alembic import context

# Alembic Config object, provides access to values within alembic.ini
config = context.config


# DATABASE_URL always comes from the environment — never hardcode credentials

database_url = os.getenv("DATABASE_URL", settings.database_url)

sync_url = database_url.replace(
    "postgresql+asyncpg://",
    "postgresql+psycopg://",
)

print(sync_url)

config.set_main_option("sqlalchemy.url", sync_url)

# No SQLAlchemy ORM models yet in Phase 1 — migrations are raw SQL (op.execute),
# so target_metadata stays None and `--autogenerate` is not used.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection, emitting SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection — the normal path."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
