"""Proves the identity-bootstrap path added alongside removing care_home_id from the
JWT (governance/decision-log.md's 2026-08-03 entry): a session that doesn't know
care_home_id yet can still resolve it from `users` by oidc_subject via
bootstrap_session()/migration 0019's identity_bootstrap_select policy, but nothing
about that policy makes `users` browsable cross-tenant, and sync_from_claims never
silently creates an account for a subject with no local row.
"""
import random
import uuid

from app.modules.identity.models import CareHome, Role
from app.modules.identity.ports import TokenClaims
from app.modules.identity.repository import UserRepository
from app.shared.database import bootstrap_session, rls_session, system_session
from app.shared.exceptions import UnauthenticatedError
from synthdata.home_setup import build_care_home


async def _seed_care_home(session, rng, name, home_id) -> None:
    data = build_care_home(rng, name)
    data["id"] = home_id
    session.add(CareHome(**data))
    await session.flush()


async def test_bootstrap_session_resolves_care_home_id_by_oidc_subject():
    home_id = uuid.uuid4()
    manager_id = uuid.uuid4()
    rng = random.Random(101)

    async with rls_session(home_id, manager_id) as session:
        await _seed_care_home(session, rng, "Bootstrap Home", home_id)
        user = await UserRepository(session).create_provisioned(
            care_home_id=home_id,
            oidc_subject="kc-subject-1",
            email="nurse@example.com",
            display_name="Nurse One",
            role=Role.NURSE,
        )

    async with bootstrap_session() as session:
        found = await UserRepository(session).find_care_home_id_by_oidc_subject("kc-subject-1")

    assert found == home_id
    assert user.oidc_subject == "kc-subject-1"


async def test_bootstrap_session_finds_nothing_for_unknown_subject():
    async with bootstrap_session() as session:
        found = await UserRepository(session).find_care_home_id_by_oidc_subject("no-such-subject")

    assert found is None


async def test_system_session_cannot_resolve_care_home_id():
    """system_session() sets no app.bootstrap flag -- confirms the new policy is
    additive to identity_bootstrap_select specifically, not a general RLS loosening
    on `users`."""
    home_id = uuid.uuid4()
    rng = random.Random(102)

    async with rls_session(home_id, uuid.uuid4()) as session:
        await _seed_care_home(session, rng, "System Session Home", home_id)
        await UserRepository(session).create_provisioned(
            care_home_id=home_id,
            oidc_subject="kc-subject-2",
            email="carer@example.com",
            display_name="Carer Two",
            role=Role.CARER,
        )

    async with system_session() as session:
        found = await UserRepository(session).find_care_home_id_by_oidc_subject("kc-subject-2")

    assert found is None


async def test_sync_from_claims_rejects_a_subject_with_no_local_row():
    claims = TokenClaims(subject="kc-unprovisioned", email="x@example.com", display_name="X", role="nurse")
    home_id = uuid.uuid4()

    async with rls_session(home_id, uuid.uuid4()) as session:
        try:
            await UserRepository(session).sync_from_claims(claims)
            raise AssertionError("expected UnauthenticatedError")
        except UnauthenticatedError:
            pass


async def test_sync_from_claims_rejects_a_deactivated_user():
    """The other half of a "deactivate staff" action actually working: is_active=False
    must block login server-side too, not just rely on the Keycloak-side disable
    (identity/service.py's update_staff_member calls both)."""
    home_id = uuid.uuid4()
    rng = random.Random(104)

    async with rls_session(home_id, uuid.uuid4()) as session:
        await _seed_care_home(session, rng, "Deactivated Home", home_id)
        user = await UserRepository(session).create_provisioned(
            care_home_id=home_id,
            oidc_subject="kc-subject-4",
            email="deactivated@example.com",
            display_name="Deactivated User",
            role=Role.CARER,
        )
        user.is_active = False
        await session.flush()

    claims = TokenClaims(subject="kc-subject-4", email="deactivated@example.com", display_name="X", role="carer")
    async with rls_session(home_id, uuid.uuid4()) as session:
        try:
            await UserRepository(session).sync_from_claims(claims)
            raise AssertionError("expected UnauthenticatedError")
        except UnauthenticatedError:
            pass


async def test_sync_from_claims_resyncs_identity_fields_for_an_existing_row():
    home_id = uuid.uuid4()
    rng = random.Random(103)

    async with rls_session(home_id, uuid.uuid4()) as session:
        await _seed_care_home(session, rng, "Resync Home", home_id)
        await UserRepository(session).create_provisioned(
            care_home_id=home_id,
            oidc_subject="kc-subject-3",
            email="old@example.com",
            display_name="Old Name",
            role=Role.CARER,
        )

    claims = TokenClaims(subject="kc-subject-3", email="new@example.com", display_name="New Name", role="nurse")
    async with rls_session(home_id, uuid.uuid4()) as session:
        user = await UserRepository(session).sync_from_claims(claims)

    assert user.email == "new@example.com"
    assert user.display_name == "New Name"
    assert user.role == Role.NURSE
    assert user.care_home_id == home_id
