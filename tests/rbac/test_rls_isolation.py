"""Proves cross-tenant isolation and audit immutability against a real Postgres
instance -- never mocked, since the whole point is the DB enforcing the boundary even
if application code is compromised. Requires the RLS policies and audit trigger from
migrations/README.md to exist, so this is skipped until migrations land.
"""

import pytest

pytestmark = pytest.mark.skip(reason="requires testcontainers Postgres + applied Alembic migrations")


async def test_session_without_rls_context_sees_zero_rows():
    """A session that never calls rls_session() must see zero rows on any tenant
    table, per app/shared/database.py's docstring -- this is the property the whole
    RLS design rests on."""
    raise NotImplementedError


async def test_session_scoped_to_one_care_home_cannot_see_another():
    raise NotImplementedError


async def test_audit_events_reject_update():
    raise NotImplementedError


async def test_audit_events_reject_delete():
    raise NotImplementedError
