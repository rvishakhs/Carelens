from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from intelligence.api.dependencies import actor
from intelligence.connectors.staff_identity import (
    CareLensStaffIdentityReader,
    StaffAccessDenied,
    StaffIdentityUnavailable,
    StaffUnauthenticated,
)
from intelligence.core.contracts import Scope


def make_app(reader):
    app = FastAPI()
    app.state.staff_identity_reader = reader
    reached = []

    @app.get("/protected")
    async def protected(scope: Scope = Depends(actor)):
        reached.append(scope)
        return scope.model_dump(mode="json")

    return app, reached


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Basic invalid"}, {"Authorization": "Bearer "},
])
def test_missing_or_wrong_scheme_blocks_route(headers):
    reader = SimpleNamespace(resolve=AsyncMock())
    app, reached = make_app(reader)
    with TestClient(app) as client:
        response = client.get("/protected", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    reader.resolve.assert_not_awaited()
    assert reached == []


def test_preserves_trusted_identity_despite_spoofed_query():
    scope = Scope(tenant_id=uuid4(), actor_id=uuid4(), resident_ids={uuid4()},
                  permissions={"handover:generate"})
    reader = SimpleNamespace(resolve=AsyncMock(return_value=scope))
    app, reached = make_app(reader)
    with TestClient(app) as client:
        response = client.get(
            "/protected", params={"tenant_id": str(uuid4()), "actor_id": str(uuid4())},
            headers={"Authorization": "Bearer test-staff-token"},
        )
    assert response.status_code == 200
    assert response.json() == scope.model_dump(mode="json")
    reader.resolve.assert_awaited_once_with("test-staff-token")
    assert reached == [scope]


@pytest.mark.parametrize(("error", "status"), [
    (StaffUnauthenticated, 401), (StaffAccessDenied, 403), (StaffIdentityUnavailable, 503),
])
def test_identity_failure_blocks_route(error, status):
    reader = SimpleNamespace(resolve=AsyncMock(side_effect=error()))
    app, reached = make_app(reader)
    with TestClient(app) as client:
        response = client.get("/protected", headers={"Authorization": "Bearer test-staff-token"})
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert "test-staff-token" not in response.text
    assert reached == []


@pytest.mark.parametrize(("upstream_status", "body", "expected_status"), [
    (401, {}, 401), (403, {}, 403), (503, {}, 503), (200, {}, 503),
])
def test_real_connector_failure_blocks_api(upstream_status, body, expected_status):
    # Exercise both layers together, mocking only the outbound HTTP transport.
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(upstream_status, json=body)
        )) as upstream:
            reader = CareLensStaffIdentityReader(client=upstream, base_url="https://carelens.test")
            app, reached = make_app(reader)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test",
            ) as client:
                response = await client.get("/protected", headers={"Authorization": "Bearer old-demo-token"})
            assert response.status_code == expected_status
            assert reached == []
    import asyncio
    asyncio.run(check())
