import asyncio
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from intelligence.connectors.carelens import CareLensClient, CareLensPaginationIncomplete, CareLensUnavailable
from intelligence.connectors.normalise import normalise_observation
from intelligence.core.contracts import Period
from intelligence.handover.metrics import calculate_handover_metrics
from intelligence.handover.rendering import render_evidence
from intelligence.handover.retrieval import retrieve_shift_observations
from tests.support.carelens import RESIDENT_ID, context, observation

SHIFT = Period(start="2026-10-07T19:00:00+01:00", end="2026-10-08T07:00:00+01:00")


def option(section, label):
    return dict(option_id=str(uuid4()), section_id=str(uuid4()), section_name=section, label=label)


def event(name="Drink", category="Nutrition & Hydration", options=None, **changes):
    value = dict(
        template_id=str(uuid4()),
        category_id=str(uuid4()),
        template_name=name,
        category_name=category,
        status="completed",
        duration_minutes=5,
        created_at="2026-10-07T18:15:00Z",
        updated_at="2026-10-07T18:15:00Z",
        options=options or [],
        measurements=[],
        note="private resident name",
        summary="private summary",
    )
    value.update(changes)
    return observation(
        id=str(uuid4()),
        source_type="care_events",
        type="note",
        value=value,
        recorded_at="2026-10-07T18:15:00Z",
    )


def normalise(row):
    return normalise_observation(row, context=context(), expected_resident_id=RESIDENT_ID)


@pytest.mark.parametrize("note,mapped", [
    ("Was wandering around the garden", True),
    ("Wandering in the garden.", True),
    ("Was not wandering around the garden", False),
    ("Was wandering around the garden with Mary Smith", False),
    ("Was wandering around the garden and fell", False),
])
def test_garden_mapping_requires_exact_whole_note_without_losing_context(note, mapped):
    record = normalise(event("Wandering", "Emotional Support & Behaviour", note=note))
    assert record.clinical_data.get("wandering_in_garden", False) is mapped
    rendered = render_evidence(record, care_home_timezone="Europe/London")
    assert note not in rendered.model_dump_json()


def test_specific_options_are_controlled_flags_not_raw_text():
    record = normalise(event("Tea (meal)", options=[option("Food", "Sandwich"),
        option("Meal Size Offered", "Medium"), option("Amount Eaten", "Most")]))
    assert record.clinical_data["food_sandwich"] is True
    assert record.clinical_data["meal_size_medium"] is True
    rendered = render_evidence(record, care_home_timezone="Europe/London")
    assert all(not isinstance(f.value, str) for f in rendered.fields)


def test_five_events_retrieved_paginated_mapped_and_rendered_without_raw_text():
    rows = [
        event(options=[option("Quantity Offered", "150ml"), option("Amount", "Half")]),
        event("Tea (drink)", options=[option("Quantity Offered", "280ml"), option("Amount", "All")]),
        event("Tea (meal)", options=[option("Amount Eaten", "Most")]),
        event("Walk", "Mobility", [option("Aid Used", "Walking Frame")]),
        event("Wandering", "Emotional Support & Behaviour", [option("Response", "Settled")]),
    ]
    offsets = []

    def handler(request):
        if request.url.path.endswith("/observations"):
            return httpx.Response(200, json=[])
        assert request.url.path == "/internal/intelligence/care-events"
        assert request.url.params["tenant_id"] == str(context().tenant_id)
        assert request.url.params["since"] == SHIFT.start.isoformat()
        assert request.url.params["until"] == SHIFT.end.isoformat()
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json=[r.model_dump(mode="json") for r in rows[offset : offset + 2]])

    async def run():
        async with httpx.AsyncClient(
            base_url="https://carelens.test", transport=httpx.MockTransport(handler)
        ) as http:
            return await retrieve_shift_observations(
                CareLensClient(http, service_tenant_id=context().tenant_id),
                context=context(),
                resident_id=RESIDENT_ID,
                access_token=SecretStr("test"),
                shift=SHIFT,
                care_home_timezone="Europe/London",
                page_size=2,
            )

    result = asyncio.run(run())
    assert offsets == [0, 2, 4, 5]
    assert [r.kind for r in result.shift_records] == [
        "fluid_intake",
        "fluid_intake",
        "meal",
        "mobility",
        "behaviour",
    ]
    assert sum(r.clinical_data.get("estimated_consumed_ml", 0) for r in result.shift_records) == 355
    metrics = calculate_handover_metrics(result, retrieval_complete=False)
    assert metrics.offered.known_subtotal == 430
    assert metrics.consumed.value is None  # estimates are not exact recorded intake
    for record in result.shift_records:
        rendered = render_evidence(record, care_home_timezone="Europe/London")
        assert "private" not in rendered.model_dump_json()
        assert all(not isinstance(f.value, str) for f in rendered.fields)
        assert record.reference.source_type == "care_events"
        assert record.reference.fingerprint
    assert result.shift_records[2].clinical_data.get("percentage_eaten") is None


@pytest.mark.parametrize("status", ["declined", "refused", "not_applicable"])
def test_noncompleted_events_do_not_create_intake(status):
    record = normalise(
        event(status=status, options=[option("Quantity Offered", "150ml"), option("Amount", "All")])
    )
    assert "offered_ml" not in record.clinical_data
    assert "estimated_consumed_ml" not in record.clinical_data


def test_ambiguous_options_do_not_create_estimates():
    record = normalise(
        event(options=[option("Quantity Offered", "150ml"), option("Quantity Offered", "280ml")])
    )
    assert "offered_ml" not in record.clinical_data


@pytest.mark.parametrize("case", ["old", "end", "wrong_resident", "duplicate", "server_error"])
def test_invalid_feed_never_returns_partial_evidence(case):
    row = event().model_dump(mode="json")
    if case == "old":
        row["recorded_at"] = "2026-08-23T18:00:00Z"
    elif case == "end":
        row["recorded_at"] = SHIFT.end.isoformat()
    elif case == "wrong_resident":
        row["resident_id"] = str(uuid4())

    def handler(request):
        offset = int(request.url.params["offset"])
        if case == "server_error" and offset:
            return httpx.Response(500)
        return httpx.Response(200, json=[row])

    async def run():
        async with httpx.AsyncClient(
            base_url="https://carelens.test", transport=httpx.MockTransport(handler)
        ) as http:
            await CareLensClient(http, service_tenant_id=context().tenant_id).list_care_events(
                RESIDENT_ID,
                SecretStr("test"),
                since=SHIFT.start,
                until=SHIFT.end,
                max_pages=3,
            )

    with pytest.raises((CareLensUnavailable, CareLensPaginationIncomplete)):
        asyncio.run(run())


def test_care_event_reaches_fake_gateway_with_private_fields_withheld():
    from intelligence.gateway.handover import HandoverGateway
    from intelligence.gateway.preparation import prepare_handover
    from intelligence.handover.contracts import HandoverAgentInput, HandoverRetrieval
    from intelligence.handover.evidence import assemble_shift_evidence
    from tests.support.fake_handover import FakeHandoverProvider

    ctx = context().model_copy(update={"permissions": frozenset({"handover:generate"})})
    record = normalise(event("Wandering", "Emotional Support & Behaviour"))
    evidence = assemble_shift_evidence(
        (record,), context=ctx, expected_resident_id=RESIDENT_ID,
        period=SHIFT, care_home_timezone="Europe/London",
    )
    input = HandoverAgentInput(
        execution_context=ctx, job_id=uuid4(), resident_id=RESIDENT_ID, period=SHIFT,
        care_home_timezone="Europe/London",
        retrieval=HandoverRetrieval(evidence=evidence, retrieved_at=SHIFT.end, coverage_complete=False),
        metrics=calculate_handover_metrics(evidence, retrieval_complete=False),
    )
    payload = prepare_handover(input=input).payload.model_dump_json()
    assert "private" not in payload
    assert str(RESIDENT_ID) not in payload
    assert str(record.reference.source_id) not in payload
    result = asyncio.run(HandoverGateway(provider=FakeHandoverProvider()).generate(input=input))
    assert any(s.category == "mood_behaviour" for s in result.sections)
    assert any(record.reference in claim.sources for s in result.sections for claim in s.claims)
    assert "care_event_free_text_and_unmapped_fields_withheld" in result.warnings
