"""Proves cross-tenant isolation and audit immutability against a real Postgres
instance -- never mocked, since the whole point is the DB enforcing the boundary even
if application code is compromised. Requires the RLS policies and audit trigger from
migrations/README.md to exist, so this is skipped until migrations land.
"""
import random
import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.modules.identity.models import CareHome
from app.modules.residents.models import Resident, ResidentStatus
from app.modules.residents.repository import ResidentRepository
from app.shared.database import rls_session, system_session
from synthdata.home_setup import build_care_home

# pytestmark = pytest.mark.skip(reason="requires testcontainers Postgres + applied Alembic migrations")

######## Move This to Helper Functions (Must do) ###############

async def seed_resident(session, home_id, first_name):
    resident = Resident(
        care_home_id=home_id,
        first_name=first_name,
        last_name="Smith",
        date_of_birth=date(1945, 5, 10),
        admission_date=date.today(),
        room_number="101",
        status=ResidentStatus.ACTIVE,
    )

    session.add(resident)
    await session.flush()

    return resident

async def seed_care_home(session, rng, name, home_id):
    data = build_care_home(rng, name)
    data["id"] = home_id

    care_home = CareHome(**data)
    session.add(care_home)
    await session.flush()

    return care_home
################################################################

async def test_session_without_rls_context_sees_zero_rows():
    """A session that never calls rls_session() must see zero rows on any tenant
    table, per app/shared/database.py's docstring -- this is the property the whole
    RLS design rests on."""

    # Arrange
    home_a_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    home_b_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    user_a_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
    user_b_id = uuid.UUID("88888888-8888-8888-8888-888888888888")

    rng = random.Random(42)

    async with rls_session(home_a_id, user_a_id) as session:
        await seed_care_home(session, rng, "Home A", home_a_id)
        await seed_resident(session, home_a_id, "John" )

    async with rls_session(home_b_id, user_b_id) as session:
        await seed_care_home(session, rng, "Home B", home_b_id)
        await seed_resident(session, home_b_id, "Marry")

    # Act
    async with system_session() as session:
        result = await session.execute(text("""
                SELECT
                    current_user,
                    session_user,
                    current_setting('app.care_home_id', true);
            """))
        print(result.fetchall())

        result = await session.execute(text("""
                                            SELECT rolname,
                                                   rolsuper,
                                                   rolbypassrls
                                            FROM pg_roles
                                            WHERE rolname = current_user;
                                            """))
        print(result.fetchall())

        rows = await ResidentRepository(session).list_active_residents()

        # Assert
        assert len(rows) == 0


async def _seed_audit_event(session, home_id) -> uuid.UUID:
    result = await session.execute(
        text(
            """
            INSERT INTO audit_events (care_home_id, action, entity_type, entity_id)
            VALUES (:care_home_id, 'view', 'resident', :entity_id)
            RETURNING id
            """
        ),
        {"care_home_id": home_id, "entity_id": uuid.uuid4()},
    )
    return result.scalar_one()


async def test_audit_events_reject_update():
    """audit_events is append-only at the DB layer (migrations/versions/0009):
    trg_audit_no_update rejects UPDATE regardless of what wrote the row."""
    home_id = uuid.uuid4()
    user_id = uuid.uuid4()
    rng = random.Random(3)

    async with rls_session(home_id, user_id) as session:
        await seed_care_home(session, rng, "Audit Update Home", home_id)
        audit_id = await _seed_audit_event(session, home_id)

    with pytest.raises(Exception, match="append-only"):
        async with rls_session(home_id, user_id) as session:
            await session.execute(
                text("UPDATE audit_events SET justification = 'tampered' WHERE id = :id"),
                {"id": audit_id},
            )


async def test_audit_events_reject_delete():
    """Same guarantee as above, for DELETE (trg_audit_no_delete)."""
    home_id = uuid.uuid4()
    user_id = uuid.uuid4()
    rng = random.Random(4)

    async with rls_session(home_id, user_id) as session:
        await seed_care_home(session, rng, "Audit Delete Home", home_id)
        audit_id = await _seed_audit_event(session, home_id)

    with pytest.raises(Exception, match="append-only"):
        async with rls_session(home_id, user_id) as session:
            await session.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": audit_id})
