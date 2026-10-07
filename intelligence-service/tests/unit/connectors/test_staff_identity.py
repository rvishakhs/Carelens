import asyncio
from functools import wraps
from uuid import uuid4

import httpx
import pytest

from intelligence.connectors.staff_identity import (
    CareLensStaffIdentityReader,
    StaffAccessDenied,
    StaffIdentityUnavailable,
    StaffUnauthenticated,
)


def run_async(function):
    # Match this project's asyncio.run convention; no pytest-asyncio dependency.
    @wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return run


@run_async
async def test_resolves_real_staff_scope():
    tenant_id = uuid4()
    actor_id = uuid4()
    resident_id = uuid4()

    def handler(request):
        assert request.url.path == "/identity/intelligence-scope"
        assert request.headers["Authorization"] == "Bearer test-token"

        return httpx.Response(
            200,
            json={
                "tenant_id": str(tenant_id),
                "actor_id": str(actor_id),
                "resident_ids": [str(resident_id)],
                "permissions": ["handover:generate"],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        reader = CareLensStaffIdentityReader(
            client=client,
            base_url="https://carelens.test",
        )

        scope = await reader.resolve("test-token")

    assert scope.tenant_id == tenant_id
    assert scope.actor_id == actor_id
    assert scope.resident_ids == frozenset({resident_id})
    assert scope.permissions == frozenset({"handover:generate"})


@run_async
@pytest.mark.parametrize(
    ("status", "expected_error"),
    [
        (401, StaffUnauthenticated),
        (403, StaffAccessDenied),
        (500, StaffIdentityUnavailable),
        (503, StaffIdentityUnavailable),
        (302, StaffIdentityUnavailable),
    ],
)
async def test_rejects_unsuccessful_responses(status, expected_error):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status,
            headers={"Location": "https://other.test"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        reader = CareLensStaffIdentityReader(
            client=client,
            base_url="https://carelens.test",
        )

        with pytest.raises(expected_error):
            await reader.resolve("test-token")

    # Even when the client enables redirects, the connector must not follow.
    assert len(requests) == 1


@run_async
@pytest.mark.parametrize("body", [b"not-json", b"{}", b'{"actor_id":"invalid"}'])
async def test_rejects_malformed_scope(body):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=body)
    )

    async with httpx.AsyncClient(transport=transport) as client:
        reader = CareLensStaffIdentityReader(
            client=client,
            base_url="https://carelens.test",
        )

        with pytest.raises(StaffIdentityUnavailable):
            await reader.resolve("test-token")


@run_async
async def test_timeout_fails_closed():
    def handler(request):
        raise httpx.ReadTimeout("Test timeout", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        reader = CareLensStaffIdentityReader(
            client=client,
            base_url="https://carelens.test",
        )

        with pytest.raises(StaffIdentityUnavailable):
            await reader.resolve("test-token")

@pytest.mark.parametrize("base_url", [
    "http://remote.test", "https://user:password@carelens.test",
    "https://carelens.test?token=secret", "https://carelens.test#fragment",
])
def test_rejects_unsafe_endpoint(base_url):
    async def check():
        async with httpx.AsyncClient() as client:
            with pytest.raises(ValueError):
                CareLensStaffIdentityReader(client=client, base_url=base_url)
    asyncio.run(check())


@run_async
async def test_connection_failure_fails_closed():
    def handler(request):
        raise httpx.ConnectError("Test connection failure", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        reader = CareLensStaffIdentityReader(client=client, base_url="https://carelens.test")
        with pytest.raises(StaffIdentityUnavailable):
            await reader.resolve("test-token")
