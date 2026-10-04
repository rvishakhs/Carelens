"""One-page transport checks only; no live server or database access."""

import asyncio
import traceback
from datetime import datetime

import httpx
import pytest

from intelligence.connectors.carelens import (
    CareLensAccessDenied,
    CareLensClient,
    CareLensResourceUnavailable,
    CareLensUnavailable,
)
from tests.support.carelens import OTHER_ID, RESIDENT_ID, TOKEN, record

SINCE = datetime.fromisoformat("2026-09-08T07:00:00+01:00")
UNTIL = datetime.fromisoformat("2026-09-08T19:00:00+01:00")


def run(handler, **kwargs):
    async def exercise():
        async with httpx.AsyncClient(
            base_url="http://carelens.test",
            timeout=10,
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            return await CareLensClient(client).list_observations_page(
                RESIDENT_ID, TOKEN, **({"since": SINCE, "until": UNTIL} | kwargs)
            )

    return asyncio.run(exercise())


def test_page_filters_and_original_fields():
    def handler(request):
        assert request.url.path == "/observations"
        assert dict(request.url.params) == {
            "resident_id": str(RESIDENT_ID),
            "since": SINCE.isoformat(),
            "until": UNTIL.isoformat(),
            "limit": "20",
            "offset": "40",
        }
        assert request.headers["Authorization"] == f"Bearer {TOKEN.get_secret_value()}"
        return httpx.Response(200, json=[record()])

    rows = run(handler, limit=20, offset=40)
    assert len(rows) == 1
    assert rows[0].value == record()["value"]
    assert rows[0].source_type == "fluid_intake_records"


def test_empty_page():
    assert run(lambda _: httpx.Response(200, json=[])) == []


def test_date_only_metadata_is_preserved():
    rows = run(
        lambda _: httpx.Response(
            200,
            json=[
                record(
                    source_type="sleep_records",
                    type="sleep",
                    value={"hours": 6},
                    recorded_at="2026-09-08T00:00:00+01:00",
                    time_precision="date",
                    source_date="2026-09-08",
                )
            ],
        ),
        since=datetime.fromisoformat("2026-09-08T00:00:00+01:00"),
    )
    assert rows[0].time_precision == "date"
    assert rows[0].source_date == "2026-09-08"


@pytest.mark.parametrize(
    "status,error",
    [
        (401, CareLensAccessDenied),
        (403, CareLensAccessDenied),
        (404, CareLensResourceUnavailable),
        (429, CareLensUnavailable),
        (500, CareLensUnavailable),
        (302, CareLensUnavailable),
    ],
)
def test_errors_do_not_retry_redirect_or_expose_body(status, error):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, text="synthetic-private-marker", headers={"Location": "https://other.test/secret"}
        )

    with pytest.raises(error) as exc:
        run(handler)
    assert len(calls) == 1
    assert "synthetic-private-marker" not in "".join(traceback.format_exception(exc.value))


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        [record(value="synthetic-private-marker")],
        [record(resident_id=str(OTHER_ID))],
        [record(recorded_at="2026-09-08T08:00:00")],
        [record(recorded_at=UNTIL.isoformat())],
        [record(recorded_at="2026-09-08T06:59:00+01:00")],
    ],
)
def test_invalid_response_is_rejected_without_content(body):
    with pytest.raises(CareLensUnavailable) as exc:
        run(lambda _: httpx.Response(200, json=body))
    assert "synthetic-private-marker" not in "".join(traceback.format_exception(exc.value))


def test_invalid_json_and_network_failure():
    with pytest.raises(CareLensUnavailable):
        run(lambda _: httpx.Response(200, text="not-json"))

    def fail(request):
        raise httpx.ReadTimeout("synthetic-private-marker", request=request)

    with pytest.raises(CareLensUnavailable) as exc:
        run(fail)
    assert "synthetic-private-marker" not in "".join(traceback.format_exception(exc.value))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"since": datetime(2026, 9, 8)},
        {"until": SINCE},
        {"limit": 0},
        {"limit": 501},
        {"offset": -1},
    ],
)
def test_invalid_filters_never_dispatch(kwargs):
    def unexpected(_):
        pytest.fail("Invalid parameters must not cause an HTTP request")

    with pytest.raises(ValueError):
        run(unexpected, **kwargs)


def test_excess_page_size_is_rejected():
    with pytest.raises(CareLensUnavailable, match="page size"):
        run(lambda _: httpx.Response(200, json=[record(), record()]), limit=1)
