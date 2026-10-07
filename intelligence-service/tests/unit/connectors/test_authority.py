import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from intelligence.connectors.authority import HttpCareLensAuthorityReader, KeycloakCredentialProvider
from intelligence.connectors.carelens import CareLensClient
from intelligence.core.errors import ExecutionAuthorisationDenied, ExecutionAuthorisationUnavailable


def provider(client):
    return KeycloakCredentialProvider(
        client=client,
        token_url="https://identity.test/token",
        client_id="worker",
        client_secret=SecretStr("test-secret"),
        expected_service_identity="intelligence-api",
    )


def test_credentials_and_tenant_scoped_authority():
    tenant, resident, actor = uuid4(), uuid4(), uuid4()
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/token":
            assert b"grant_type=client_credentials" in request.content
            assert "authorization" not in request.headers
            return httpx.Response(
                200, json={"access_token": "worker-token", "token_type": "Bearer", "expires_in": 300}
            )
        assert request.headers["authorization"] == "Bearer worker-token"
        assert request.url.params["tenant_id"] == str(tenant)
        if request.url.path.endswith("/service"):
            return httpx.Response(
                200,
                json={
                    "tenant_id": str(tenant),
                    "service_identity": "intelligence-api",
                    "resident_ids": [str(resident)],
                    "permissions": ["handover:generate"],
                },
            )
        if "/staff/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "tenant_id": str(tenant),
                    "actor_id": str(actor),
                    "resident_ids": [str(resident)],
                    "permissions": ["handover:generate"],
                },
            )
        if request.url.path.endswith("/eligibility"):
            return httpx.Response(
                200, json={"tenant_id": str(tenant), "resident_id": str(resident), "eligible": True}
            )
        assert request.url.path == "/internal/intelligence/observations"
        return httpx.Response(200, json=[])

    async def run():
        async with httpx.AsyncClient(
            base_url="https://carelens.test", transport=httpx.MockTransport(handler)
        ) as client:
            credentials = await provider(client).obtain()
            assert "worker-token" not in repr(credentials)
            reader = HttpCareLensAuthorityReader(client=client, access_token=credentials.access_token)
            assert (await reader.service_grant(tenant_id=tenant)).resident_ids == frozenset({resident})
            assert (await reader.staff_grant(tenant_id=tenant, actor_id=actor)).actor_id == actor
            assert await reader.resident_eligible(tenant_id=tenant, resident_id=resident)
            now = datetime.now(UTC)
            assert (
                await CareLensClient(client, service_tenant_id=tenant).list_observations_page(
                    resident,
                    credentials.access_token,
                    since=now - timedelta(hours=12),
                    until=now,
                )
                == []
            )

    asyncio.run(run())
    assert len(seen) == 5


@pytest.mark.parametrize(
    "status,body,error",
    [
        (401, {}, ExecutionAuthorisationDenied),
        (500, {}, ExecutionAuthorisationUnavailable),
        (302, {}, ExecutionAuthorisationUnavailable),
        (200, {}, ExecutionAuthorisationUnavailable),
        (
            200,
            {"access_token": "x", "token_type": "bearer", "expires_in": 1},
            ExecutionAuthorisationUnavailable,
        ),
        (
            200,
            {"access_token": "x", "token_type": "unknown", "expires_in": 300},
            ExecutionAuthorisationUnavailable,
        ),
    ],
)
def test_credentials_fail_closed(status, body, error):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))
        ) as client:
            with pytest.raises(error):
                await provider(client).obtain()

    asyncio.run(run())


@pytest.mark.parametrize("scenario", ["wrong_scope", "string_boolean", "malformed", "unavailable", "denied"])
def test_authority_fail_closed(scenario):
    tenant, resident = uuid4(), uuid4()
    body = {"tenant_id": str(tenant), "resident_id": str(resident), "eligible": True}
    status = 200
    if scenario == "wrong_scope":
        body["tenant_id"] = str(uuid4())
    elif scenario == "string_boolean":
        body["eligible"] = "true"
    elif scenario == "malformed":
        body = {}
    elif scenario == "unavailable":
        status = 503
    elif scenario == "denied":
        status = 403

    async def run():
        async with httpx.AsyncClient(
            base_url="https://carelens.test",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(status, json=body),
            ),
        ) as client:
            reader = HttpCareLensAuthorityReader(client=client, access_token=SecretStr("test-token"))
            error = (
                ExecutionAuthorisationDenied if scenario == "denied" else ExecutionAuthorisationUnavailable
            )
            with pytest.raises(error):
                await reader.resident_eligible(tenant_id=tenant, resident_id=resident)

    asyncio.run(run())


@pytest.mark.parametrize(
    "url", ["http://remote.test/token", "https://user:pass@identity.test/token", "ftp://localhost/token"]
)
def test_credentials_reject_insecure_endpoints(url):
    from intelligence.connectors.authority import require_secure_endpoint

    with pytest.raises(ValueError):
        require_secure_endpoint(url)
