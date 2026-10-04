"""Bounded raw pagination, deliberately separate from source normalization."""

import asyncio

import httpx
import pytest

from intelligence.connectors.carelens import (
    CareLensAccessDenied,
    CareLensClient,
    CareLensPaginationIncomplete,
    CareLensUnavailable,
)
from tests.support.carelens import RESIDENT_ID, SINCE, TOKEN, UNTIL, record


def rows(count):
    return [record(id=f"40000000-0000-0000-0000-{i:012d}") for i in range(count)]


def traverse(handler, **kwargs):
    async def exercise():
        async with httpx.AsyncClient(
            base_url="http://carelens.test", transport=httpx.MockTransport(handler), timeout=10
        ) as client:
            return await CareLensClient(client).list_observations(
                RESIDENT_ID, TOKEN, since=SINCE, until=UNTIL, **kwargs
            )

    return asyncio.run(exercise())


@pytest.mark.parametrize("count,expected_offsets", [(0, [0]), (100, [0, 100]), (105, [0, 100, 105])])
def test_traversal_including_terminal_empty_page(count, expected_offsets):
    data = rows(count)
    offsets = []

    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        assert request.url.params["since"] == SINCE.isoformat()
        assert request.url.params["until"] == UNTIL.isoformat()
        assert request.headers["Authorization"] == f"Bearer {TOKEN.get_secret_value()}"
        return httpx.Response(200, json=data[offset : offset + 100])

    result = traverse(handler)
    assert len(result) == count
    assert offsets == expected_offsets


def test_short_pages_and_excluded_sources_count_towards_offset():
    data = rows(3)
    data[0]["source_type"] = "observations"
    offsets = []

    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json=data[offset : offset + 1])

    result = traverse(handler, page_size=100)
    assert offsets == [0, 1, 2, 3]
    assert len(result) == 3 and result[0].source_type == "observations"


@pytest.mark.parametrize("failure", [403, 500, "timeout", "invalid"])
def test_later_page_failure_does_not_return_partial_data(failure):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json=rows(1))
        if failure == "timeout":
            raise httpx.ReadTimeout("private text", request=request)
        if failure == "invalid":
            return httpx.Response(200, json={"wrong": "shape"})
        return httpx.Response(failure)

    with pytest.raises(CareLensAccessDenied if failure == 403 else CareLensUnavailable):
        traverse(handler)
    assert len(calls) == 2


@pytest.mark.parametrize("same_page", [True, False])
def test_repeated_identity_fails_instead_of_deduplicating(same_page):
    def handler(_):
        return httpx.Response(200, json=[record(), record()] if same_page else [record()])

    with pytest.raises(CareLensPaginationIncomplete, match="duplicate"):
        traverse(handler)


def test_same_uuid_in_different_sources_is_not_duplicate():
    def handler(request):
        return httpx.Response(
            200,
            json=[] if int(request.url.params["offset"]) else [record(), record(source_type="observations")],
        )

    assert len(traverse(handler)) == 2


def test_page_budget_includes_empty_page_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=rows(1))

    with pytest.raises(CareLensPaginationIncomplete, match="page limit"):
        traverse(handler, max_pages=1)
    assert len(calls) == 1
    assert traverse(lambda _: httpx.Response(200, json=[]), max_pages=1) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_pages": 0},
        {"max_pages": 1001},
        {"max_pages": True},
        {"page_size": 0},
        {"page_size": 501},
        {"page_size": 1.5},
    ],
)
def test_invalid_bounds_never_dispatch(kwargs):
    def handler(_):
        pytest.fail("Unexpected HTTP call")

    with pytest.raises(ValueError):
        traverse(handler, **kwargs)
