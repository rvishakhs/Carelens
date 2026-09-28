import asyncio
from datetime import date

import httpx
import pytest
from pydantic import SecretStr

from intelligence.connectors.carelens import CareLensClient, CareLensUnavailable
from intelligence.core.contracts import Period
from intelligence.handover.evidence import EvidenceValidationError
from intelligence.handover.retrieval import retrieve_shift_observations
from tests.carelens_connector.test_normalise import RESIDENT_ID, context, observation


def run(handler, execution_context=None):
    async def exercise():
        async with httpx.AsyncClient(
            base_url="http://carelens.test", transport=httpx.MockTransport(handler)
        ) as http:
            return await retrieve_shift_observations(
                CareLensClient(http),
                context=execution_context or context(),
                resident_id=RESIDENT_ID,
                access_token=SecretStr("synthetic-token"),
                shift=Period(start="2026-09-08T07:00:00+01:00", end="2026-09-08T19:00:00+01:00"),
                care_home_timezone="Europe/London",
                page_size=2,
            )

    return asyncio.run(exercise())


def test_expanded_paginated_fetch_retains_date_context_and_filters_timestamps():
    def row(number, **changes):
        return observation(id=f"40000000-0000-0000-0000-{number:012d}", **changes).model_dump(mode="json")

    rows = [
        row(
            1,
            source_type="wound_records",
            type="wound",
            value={"location": "left shin"},
            time_precision="date",
            source_date="2026-09-08",
            recorded_at="2026-09-08T00:00:00+01:00",
        ),
        row(2, recorded_at="2026-09-08T06:59:00+01:00"),
        row(3, recorded_at="2026-09-08T07:00:00+01:00"),
        row(4, recorded_at="2026-09-08T19:00:00+01:00"),
        row(5, source_type="observations"),
    ]
    offsets = []

    def handler(request):
        assert request.url.params["since"] == "2026-09-08T00:00:00+01:00"
        assert request.url.params["until"] == "2026-09-09T00:00:00+01:00"
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json=rows[offset : offset + 2])

    result = run(handler)
    assert offsets == [0, 2, 4, 5]
    assert len(result.shift_records) == 1
    assert str(result.shift_records[0].reference.source_id).endswith("000000000003")
    assert len(result.date_context) == 1
    assert result.date_context[0].source_date == date(2026, 9, 8)
    assert result.date_context[0].effective_at is None
    assert result.outside_shift_count == 2
    assert result.unknown_time_records == ()
    assert result.warnings


def test_scope_denial_never_dispatches():
    def handler(_):
        pytest.fail("Out-of-scope retrieval must not make HTTP calls")

    with pytest.raises(EvidenceValidationError):
        run(handler, context().model_copy(update={"authorised_resident_ids": frozenset()}))


def test_later_page_failure_never_returns_partial_assembly():
    def handler(request):
        if int(request.url.params["offset"]) == 0:
            return httpx.Response(200, json=[observation().model_dump(mode="json")])
        return httpx.Response(500, text="private content")

    with pytest.raises(CareLensUnavailable):
        run(handler)


def test_empty_retrieval_returns_empty_collections():
    result = run(lambda _: httpx.Response(200, json=[]))
    assert result.shift_records == result.date_context == result.unknown_time_records == ()
    assert result.outside_shift_count == 0
