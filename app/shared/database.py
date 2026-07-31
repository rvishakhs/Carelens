"""Session management + Row-Level Security context.

RLS policies themselves live in Alembic migrations (DDL, not ORM-representable).
See migrations/README.md for the CREATE POLICY pattern every tenant table must follow.

The one rule that makes RLS real: a session that never calls `rls_session()` sets no
`app.care_home_id`, so every policy predicate evaluates false and the session sees zero
rows. There is no code path that bypasses this by accident.
"""

import contextlib
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TenantMixin:
    """Common columns for every tenant-scoped table. care_home_id is what RLS filters on."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str, pool_size: int = 10) -> AsyncEngine:
    global _engine, _session_factory
    _engine = create_async_engine(database_url, pool_pre_ping=True, pool_size=pool_size)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    if _engine is not None:
        await _engine.dispose()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database engine not initialised; call init_engine() at startup")
    return _session_factory


@contextlib.asynccontextmanager
async def rls_session(
    care_home_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    floor_ids: Sequence[uuid.UUID | str] | None = None,
) -> AsyncIterator[AsyncSession]:
    """Yield a session scoped to a tenant + actor (+ authorised floors) via Postgres
    session-local GUCs.

    `floor_ids` should be the caller's *authorised* floors (migrations/versions/0013's
    user_floor_links), not necessarily "every floor in the home" -- floor-scoped tables
    (most resident-linked ones, as of migration 0013) filter on `app.floor_ids` and see
    zero rows for any floor not in this list. Omitting it entirely (the default) is
    only safe for tables that aren't floor-scoped (users, floors, user_floor_links,
    audit_events, ...) -- everything else will silently return nothing.

    Use for every request-scoped unit of work. Values set via set_config(..., true)
    are cleared when the surrounding transaction ends, so nothing leaks across pooled
    connections.
    """
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        # SET LOCAL doesn't accept bind parameters (Postgres requires a literal
        # there); set_config() is the parameterized equivalent -- same effect, safe
        # with untrusted input, and scoped to the transaction via is_local=true.
        await session.execute(text("SELECT set_config('app.care_home_id', :chi, true)"), {"chi": str(care_home_id)})
        await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})
        floor_ids_csv = ",".join(str(f) for f in floor_ids) if floor_ids else ""
        await session.execute(text("SELECT set_config('app.floor_ids', :fids, true)"), {"fids": floor_ids_csv})
        yield session


@contextlib.asynccontextmanager
async def system_session() -> AsyncIterator[AsyncSession]:
    """Session with no tenant context set -- by RLS design this sees zero rows on tenant
    tables. Only for cross-tenant system operations (e.g. platform-level admin, migrations
    helpers) that go through explicitly unprotected tables."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session