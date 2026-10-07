"""Offline security tests; run with --confcutdir=tests/unit/intelligence_service."""

import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwk, jwt

from app.modules.identity import intelligence_router as routes
from app.modules.identity.service_grants import IntelligenceServiceGrant


@pytest.fixture
def setup(monkeypatch):
    grant = IntelligenceServiceGrant(
        client_id="worker",
        subject=uuid4(),
        service_identity="intelligence-api",
        tenant_id=uuid4(),
        floor_ids={uuid4()},
        resident_ids={uuid4()},
        permissions={"handover:generate"},
    )
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwk.construct(private.public_key(), "RS256").to_dict()
    settings = SimpleNamespace(
        intelligence_service_grants=[grant],
        oidc_issuer="https://identity.test/realms/carelens",
        intelligence_service_audience="carelens-intelligence-api",
    )
    claims = {
        "iss": settings.oidc_issuer,
        "aud": settings.intelligence_service_audience,
        "sub": str(grant.subject),
        "azp": grant.client_id,
        "exp": int(time.time()) + 300,
    }
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    actual_client = httpx.AsyncClient
    monkeypatch.setattr(
        routes.httpx,
        "AsyncClient",
        lambda **kwargs: actual_client(
            **kwargs,
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"keys": [public]})),
        ),
    )
    session = AsyncMock()
    session.scalar.return_value = grant.tenant_id
    scopes = []

    @asynccontextmanager
    async def scoped(*args):
        scopes.append(args)
        yield session

    monkeypatch.setattr(routes, "rls_session", scoped)
    return grant, private, claims, session, scopes, settings


async def authenticate(grant, private, claims):
    return await routes.service_scope(
        tenant_id=grant.tenant_id,
        response=Response(),
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=jwt.encode(claims, private, "RS256")),
    )


async def test_valid_service_identity_uses_tenant_rls(setup):
    grant, private, claims, session, scopes, _ = setup
    assert await authenticate(grant, private, claims) == grant
    assert scopes == [(grant.tenant_id, grant.subject)]


@pytest.mark.parametrize(
    "field,value",
    [
        ("aud", "staff-web"),
        ("iss", "https://wrong.test"),
        ("sub", str(uuid4())),
        ("azp", "admin-client"),
        ("exp", 1),
        ("exp", None),
        ("aud", None),
    ],
)
async def test_wrong_or_expired_identity_is_denied(setup, field, value):
    grant, private, claims, session, scopes, _ = setup
    if value is None:
        claims.pop(field)
    else:
        claims[field] = value
    with pytest.raises(HTTPException) as error:
        await authenticate(grant, private, claims)
    assert error.value.status_code in {401, 403}
    assert not scopes


async def test_unregistered_tenant_denied_before_database(setup):
    grant, private, claims, session, scopes, settings = setup
    settings.intelligence_service_grants = []
    with pytest.raises(HTTPException) as error:
        await authenticate(grant, private, claims)
    assert error.value.status_code == 403
    assert not scopes


async def test_deleted_home_denied(setup):
    grant, private, claims, session, scopes, _ = setup
    session.scalar.return_value = None
    with pytest.raises(HTTPException) as error:
        await authenticate(grant, private, claims)
    assert error.value.status_code == 403


async def test_inactive_staff_denied(setup):
    grant, _, _, session, _, _ = setup
    actor = uuid4()
    grant = grant.model_copy(update={"generating_staff_ids": frozenset({actor})})
    session.scalar.return_value = None
    with pytest.raises(HTTPException) as error:
        await routes.staff_grant(actor_id=actor, grant=grant)
    assert error.value.status_code == 403


async def test_staff_requires_current_permissions_and_explicit_designation(setup, monkeypatch):
    grant, _, _, session, _, _ = setup
    actor = uuid4()
    with pytest.raises(HTTPException):
        await routes.staff_grant(actor_id=actor, grant=grant)
    grant = grant.model_copy(update={"generating_staff_ids": frozenset({actor})})
    session.scalar.return_value = SimpleNamespace(role="nurse")
    session.scalars.return_value = SimpleNamespace(all=lambda: ["view_handover", "view_resident"])
    with pytest.raises(HTTPException):
        await routes.staff_grant(actor_id=actor, grant=grant)
    session.scalars.return_value = SimpleNamespace(all=lambda: ["view_handover", "view_resident", "view_observation"])
    visible = AsyncMock(return_value=[])
    monkeypatch.setattr(routes, "visible_residents", visible)
    result = await routes.staff_grant(actor_id=actor, grant=grant)
    assert result["resident_ids"] == []
    visible.assert_awaited_once_with(grant, staff_id=actor)


async def test_eligibility_requires_enrolment_visibility_and_active_record(setup, monkeypatch):
    grant, _, _, session, scopes, _ = setup
    resident = next(iter(grant.resident_ids))
    assert not await routes.is_eligible(grant, resident)
    grant = grant.model_copy(update={"eligible_resident_ids": frozenset({resident})})
    visible = AsyncMock(return_value=[])
    monkeypatch.setattr(routes, "visible_residents", visible)
    assert not await routes.is_eligible(grant, resident)
    visible.return_value = [resident]
    session.scalar.return_value = None
    assert not await routes.is_eligible(grant, resident)
    session.scalar.return_value = resident
    assert await routes.is_eligible(grant, resident)
    assert scopes[-1] == (grant.tenant_id, grant.subject, list(grant.floor_ids))


async def test_observation_route_does_not_read_ineligible_resident(setup, monkeypatch):
    from datetime import UTC, datetime, timedelta

    grant, _, _, session, scopes, _ = setup
    monkeypatch.setattr(routes, "is_eligible", AsyncMock(return_value=False))
    now = datetime.now(UTC)
    with pytest.raises(HTTPException) as error:
        await routes.observations(
            resident_id=uuid4(),
            since=now - timedelta(hours=12),
            until=now,
            grant=grant,
        )
    assert error.value.status_code == 403
    assert not scopes


async def test_http_contract_uses_real_service_dependency(setup):
    grant, private, claims, session, scopes, _ = setup
    app = FastAPI()
    app.include_router(routes.router)
    token = jwt.encode(claims, private, "RS256")
    # Use ASGITransport directly, since the identity client factory is patched.
    async with _asgi_client(app) as client:
        response = await client.get(
            f"/internal/intelligence/authority/residents/{uuid4()}/eligibility",
            params={"tenant_id": str(grant.tenant_id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["eligible"] is False
    assert response.headers["cache-control"] == "no-store"


# Keep an unpatched constructor for the ASGI test.
_ActualAsyncClient = httpx.AsyncClient


def _asgi_client(app):
    return _ActualAsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://carelens.test")


async def test_wrong_signature_is_rejected(setup):
    grant, _, claims, _, scopes, _ = setup
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException) as error:
        await authenticate(grant, other_key, claims)
    assert error.value.status_code == 401
    assert not scopes


async def test_empty_home_configuration_is_safe():
    from app.config import Settings

    settings = Settings(_env_file=None, DATABASE_URL="postgresql://unused", intelligence_service_grants=[])
    assert settings.intelligence_service_grants == []


async def test_observation_feed_uses_scoped_repository(setup, monkeypatch):
    from datetime import UTC, datetime, timedelta

    grant, _, _, session, scopes, _ = setup
    resident = next(iter(grant.resident_ids))
    monkeypatch.setattr(routes, "is_eligible", AsyncMock(return_value=True))
    repository = SimpleNamespace(list_for_resident=AsyncMock(return_value=[]))
    monkeypatch.setattr(routes, "ObservationRepository", lambda received: repository if received is session else None)
    now = datetime.now(UTC)
    result = await routes.observations(
        resident_id=resident,
        since=now - timedelta(hours=12),
        until=now,
        limit=50,
        offset=100,
        grant=grant,
    )
    assert result == []
    assert scopes == [(grant.tenant_id, grant.subject, list(grant.floor_ids))]
    repository.list_for_resident.assert_awaited_once_with(
        resident,
        50,
        offset=100,
        since=now - timedelta(hours=12),
        until=now,
    )
