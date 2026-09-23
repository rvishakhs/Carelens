"""Resident-read transport contracts; no server, database or real credentials required."""

import asyncio
import traceback
from collections.abc import Callable
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from intelligence.connectors.carelens import (
    CareLensAccessDenied,
    CareLensClient,
    CareLensResourceUnavailable,
    CareLensUnavailable,
    ResidentResponse,
)

RESIDENT_ID = UUID("30000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("30000000-0000-0000-0000-000000000002")
TOKEN = SecretStr("synthetic-test-token-not-a-real-credential")
SENSITIVE_BODY = "synthetic-private-response-marker"
Handler = Callable[[httpx.Request], httpx.Response]


def read_resident(handler: Handler, *, follow_redirects: bool = False) -> ResidentResponse:
    async def exercise() -> ResidentResponse:
        async with httpx.AsyncClient(
            base_url="http://carelens.test",
            transport=httpx.MockTransport(handler),
            timeout=10.0,
            follow_redirects=follow_redirects,
        ) as http_client:
            return await CareLensClient(http_client).get_resident(RESIDENT_ID, TOKEN)

    return asyncio.run(exercise())


def test_get_resident_sends_scoped_get_and_validates_response() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url == httpx.URL(f"http://carelens.test/residents/{RESIDENT_ID}")
        assert request.headers["Authorization"] == f"Bearer {TOKEN.get_secret_value()}"
        assert request.content == b""
        assert request.extensions["timeout"]["read"] == 10.0
        return httpx.Response(200, json={"id": str(RESIDENT_ID), "display_name": SENSITIVE_BODY})

    resident = read_resident(respond)
    assert resident.id == RESIDENT_ID
    assert resident.model_dump() == {"id": RESIDENT_ID}
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("status", "error", "message"),
    [
        (401, CareLensAccessDenied, "CareLens rejected access"),
        (403, CareLensAccessDenied, "CareLens rejected access"),
        (404, CareLensResourceUnavailable, "Resident unavailable"),
        (204, CareLensUnavailable, "CareLens returned an unexpected response"),
        (429, CareLensUnavailable, "CareLens returned an unexpected response"),
        (500, CareLensUnavailable, "CareLens returned an unexpected response"),
        (503, CareLensUnavailable, "CareLens returned an unexpected response"),
    ],
)
def test_status_mapping_does_not_expose_body_or_retry(
    status: int, error: type[Exception], message: str, caplog: pytest.LogCaptureFixture
) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, text=f"{SENSITIVE_BODY} {TOKEN.get_secret_value()}")

    with pytest.raises(error) as exc:
        read_resident(respond)
    assert str(exc.value) == message
    assert len(requests) == 1
    assert SENSITIVE_BODY not in caplog.text
    assert TOKEN.get_secret_value() not in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        b"not-json-synthetic-private-response-marker",
        b"",
        b"null",
        b"[]",
        b"{}",
        b'{"id": null}',
        b'{"id": "synthetic-private-response-marker"}',
        b'{"id": 123}',
    ],
)
def test_invalid_success_body_is_a_sanitised_error(body: bytes) -> None:
    with pytest.raises(CareLensUnavailable) as exc:
        read_resident(lambda _: httpx.Response(200, content=body))
    assert str(exc.value) == "CareLens returned an invalid resident response"
    # Standard exception formatting must not expose Pydantic's input or JSON body.
    assert SENSITIVE_BODY not in "".join(traceback.format_exception(exc.value))
    assert exc.value.__suppress_context__ is True


def test_mismatched_resident_is_rejected() -> None:
    with pytest.raises(CareLensUnavailable) as exc:
        read_resident(lambda _: httpx.Response(200, json={"id": str(OTHER_ID)}))
    assert str(exc.value) == "CareLens returned an unexpected resident"
    assert str(OTHER_ID) not in str(exc.value)


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout])
def test_network_failure_is_sanitised_and_not_retried(failure: type[httpx.RequestError]) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise failure(f"{SENSITIVE_BODY} {TOKEN.get_secret_value()}", request=request)

    with pytest.raises(CareLensUnavailable) as exc:
        read_resident(respond)
    assert str(exc.value) == "CareLens could not be reached"
    formatted = "".join(traceback.format_exception(exc.value))
    assert SENSITIVE_BODY not in formatted
    assert TOKEN.get_secret_value() not in formatted
    assert len(requests) == 1


@pytest.mark.parametrize("target", ["/unexpected-resident", "https://other-host.test/resident"])
def test_redirect_is_never_followed_even_if_client_enables_it(target: str) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(302, headers={"Location": target})
        return httpx.Response(200, json={"id": str(RESIDENT_ID)})

    with pytest.raises(CareLensUnavailable, match="unexpected response"):
        read_resident(respond, follow_redirects=True)
    assert len(requests) == 1


def test_tokens_are_per_request_and_client_remains_open() -> None:
    async def exercise() -> None:
        observed = []

        def respond(request: httpx.Request) -> httpx.Response:
            observed.append(request.headers["Authorization"])
            return httpx.Response(200, json={"id": str(RESIDENT_ID)})

        async with httpx.AsyncClient(
            base_url="http://carelens.test", transport=httpx.MockTransport(respond)
        ) as client:
            connector = CareLensClient(client)
            await connector.get_resident(RESIDENT_ID, SecretStr("first-synthetic-token"))
            await connector.get_resident(RESIDENT_ID, SecretStr("second-synthetic-token"))
            assert not client.is_closed
            assert "Authorization" not in client.headers
        assert observed == ["Bearer first-synthetic-token", "Bearer second-synthetic-token"]

    asyncio.run(exercise())
