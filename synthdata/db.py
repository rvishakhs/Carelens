"""Reflects the live Postgres schema instead of hand-duplicating it. Table objects
here are read straight off the database your Alembic migrations built -- if a
migration adds a column or changes an enum, this picks it up automatically the next
time the generator runs; nothing in synthdata/ needs editing to stay in sync.

Sessions are synchronous (psycopg, not asyncpg) -- this is a batch CLI tool, not a
request-serving path, and executemany-style batch inserts are simpler to reason
about without asyncio in the mix.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Enum, MetaData, Table, create_engine, text
from sqlalchemy.engine import Connection, Engine

_INSERT_BATCH_SIZE = 1000


def sync_database_url(async_url: str) -> str:
    """app/config.py's DATABASE_URL is asyncpg-flavoured for the running app;
    Alembic's migrations/env.py does this same swap for the same reason."""
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def build_engine(database_url: str) -> Engine:
    return create_engine(sync_database_url(database_url))


class Schema:
    """Lazily reflects every table in `public` on construction. Table objects are the
    single source of truth for column names, types, and enum labels."""

    def __init__(self, engine: Engine):
        self.metadata = MetaData()
        self.metadata.reflect(bind=engine)

    def __getitem__(self, table_name: str) -> Table:
        return self.metadata.tables[table_name]

    def enum_values(self, table_name: str, column_name: str) -> list[str]:
        """Reads the actual allowed labels for a Postgres ENUM column -- useful for
        asserting a hardcoded distribution (e.g. in reference_data.py) never drifts
        from what a migration actually created."""
        column_type = self[table_name].columns[column_name].type
        if not isinstance(column_type, Enum):
            raise TypeError(f"{table_name}.{column_name} is not an enum column")
        return list(column_type.enums)


@contextmanager
def tenant_transaction(engine: Engine, care_home_id: uuid.UUID, actor_user_id: uuid.UUID) -> Iterator[Connection]:
    """Mirrors app/shared/database.py's rls_session(): sets the same session-local
    GUCs the RLS policies check, inside one transaction. Not strictly required for
    the bootstrap Postgres role (it has BYPASSRLS -- see migrations/README.md), but
    keeping this identical to the app's own access pattern means the generator keeps
    working unchanged if it's ever run under a locked-down role."""
    with engine.begin() as conn:
        # SET LOCAL doesn't accept bind parameters (Postgres requires a literal there);
        # set_config() is the parameterized equivalent -- same effect, safe with
        # untrusted input, and scoped to the transaction via is_local=true.
        conn.execute(text("SELECT set_config('app.care_home_id', :chi, true)"), {"chi": str(care_home_id)})
        conn.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(actor_user_id)})
        yield conn


def insert_rows(conn: Connection, table: Table, rows: list[dict]) -> None:
    """Batch insert, chunked to keep any single statement's parameter count sane on
    tables that accumulate tens of thousands of rows (e.g. medication_events)."""
    if not rows:
        return
    for start in range(0, len(rows), _INSERT_BATCH_SIZE):
        chunk = rows[start : start + _INSERT_BATCH_SIZE]
        conn.execute(table.insert(), chunk)


def insert_many(conn: Connection, schema: Schema, rows_by_table: dict[str, list[dict]]) -> None:
    """Convenience for the common case: insert into several tables in one call,
    skipping any table with no rows this round."""
    for table_name, rows in rows_by_table.items():
        insert_rows(conn, schema[table_name], rows)
