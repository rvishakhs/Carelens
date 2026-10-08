import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from intelligence.gateway.contracts import CalculatedMetric, HandoverOutput
from intelligence.gateway.preparation import prepare_handover
from intelligence.gateway.privacy import PrivacyRejected, ReviewedTextPolicy
from intelligence.gateway.pseudonymisation import AliasContext, PseudonymisationError
from intelligence.gateway.resolution import resolve_handover
from intelligence.gateway.validation import (
    InboundValidationError,
    OutboundValidationError,
    validate_inbound_output,
    validate_outbound_payload,
)
from intelligence.handover.metrics import calculate_handover_metrics
from tests.support.fake_handover import FakeHandoverProvider
from tests.support.handover import make_input, replace_evidence, with_notes


def run_fake(prepared):
    return asyncio.run(FakeHandoverProvider().generate(prepared.payload))


def test_prepare_fake_validate_resolve():
    value = make_input()
    prepared = prepare_handover(input=value)
    output = run_fake(prepared)
    result = resolve_handover(prepared=prepared, output=output)
    assert result.sections[0].category == "nutrition_hydration"
    assert result.sections[0].claims[0].sources == (value.retrieval.evidence.shift_records[0].reference,)
    assert result.warnings == prepared.warnings
    assert not result.coverage_complete
    wire = prepared.payload.model_dump_json()
    assert str(value.resident_id) not in wire
    assert str(value.execution_context.tenant_id) not in wire


def test_unreviewed_text_stops_before_provider():
    calls = []

    async def pipeline():
        prepared = prepare_handover(input=with_notes("Mary Smith drank water"))
        calls.append(True)
        return await FakeHandoverProvider().generate(prepared.payload)

    with pytest.raises(PrivacyRejected):
        asyncio.run(pipeline())
    assert calls == []


def test_exact_reviewed_replacement_and_private_warning():
    value = with_notes("Mary Smith drank water")
    value = value.model_copy(
        update={
            "retrieval": value.retrieval.model_copy(
                update={"warnings": ("Internal warning about Mary Smith",)}
            )
        }
    )
    prepared = prepare_handover(
        input=value, text_policy=ReviewedTextPolicy({"Mary Smith drank water": "Resident drank water"})
    )
    assert "Mary Smith" not in prepared.payload.model_dump_json()
    result = resolve_handover(prepared=prepared, output=run_fake(prepared))
    assert "Internal warning about Mary Smith" in result.warnings


@pytest.mark.parametrize("replacement", ["test@example.com", str(uuid4()), "https://private.example"])
def test_reviewed_replacement_still_scanned(replacement):
    with pytest.raises(PrivacyRejected):
        prepare_handover(input=with_notes("note"), text_policy=ReviewedTextPolicy({"note": replacement}))


@pytest.mark.parametrize(
    "variant",
    [
        "resident",
        "source",
        "duplicate_source",
        "metric",
        "category",
        "context",
        "text",
        "duplicate_claim",
        "metric_sources",
    ],
)
def test_provider_corruption(variant):
    prepared = prepare_handover(input=make_input())
    output = run_fake(prepared)
    claim = output.claims[0]
    if variant == "resident":
        output = output.model_copy(update={"resident_alias": "RESIDENT_999"})
    elif variant == "duplicate_claim":
        output = output.model_copy(update={"claims": (claim, claim)})
    else:
        changes = {
            "source": {"source_aliases": ("SRC_999",)},
            "duplicate_source": {"source_aliases": ("SRC_001", "SRC_001")},
            "metric": {"metric_aliases": ("METRIC_999",)},
            "category": {"section": "mobility"},
            "context": {"context": "date_context"},
            "text": {"text": "Resident had a fall at 18:00"},
            "metric_sources": {"metric_aliases": ("METRIC_002",)},
        }[variant]
        output = output.model_copy(update={"claims": (claim.model_copy(update=changes),)})
    with pytest.raises(InboundValidationError):
        validate_inbound_output(output=output, payload=prepared.payload)


def test_source_fingerprint_conflict():
    reference = make_input().retrieval.evidence.shift_records[0].reference
    aliases = AliasContext()
    aliases.alias_source(reference)
    with pytest.raises(PseudonymisationError):
        aliases.alias_source(reference.model_copy(update={"fingerprint": "changed"}))


def test_metric_contract_rejects_complete_value_on_partial():
    with pytest.raises(ValidationError):
        CalculatedMetric(
            metric_alias="METRIC_001",
            metric="consumed_ml",
            status="partial",
            value=Decimal(1),
            known_subtotal=Decimal(1),
        )


def test_metric_unknown_source_and_coverage_conflict():
    payload = prepare_handover(input=make_input()).payload
    metric = payload.metrics[0]
    for update in ({"source_aliases": ("SRC_999",)}, {"status": "complete", "value": metric.known_subtotal}):
        with pytest.raises(OutboundValidationError):
            validate_outbound_payload(
                payload.model_copy(update={"metrics": (metric.model_copy(update=update),)})
            )


def test_empty_evidence():
    value = make_input()
    evidence = value.retrieval.evidence.model_copy(update={"shift_records": ()})
    value = replace_evidence(value, evidence).model_copy(
        update={"metrics": calculate_handover_metrics(evidence, retrieval_complete=False)}
    )
    prepared = prepare_handover(input=value)
    output = run_fake(prepared)
    assert output.claims == ()
    assert resolve_handover(prepared=prepared, output=output).sections == ()


def test_output_limits_rechecked_after_model_copy():
    prepared = prepare_handover(input=make_input())
    output = run_fake(prepared)
    for changes in (
        {"claims": output.claims * 81},
        {"claims": (output.claims[0].model_copy(update={"text": "x" * 2001}),)},
    ):
        with pytest.raises(InboundValidationError):
            validate_inbound_output(output=output.model_copy(update=changes), payload=prepared.payload)


def test_missing_claims_rejected():
    prepared = prepare_handover(input=make_input())
    with pytest.raises(InboundValidationError):
        resolve_handover(
            prepared=prepared,
            output=HandoverOutput(resident_alias=prepared.payload.resident_alias, claims=()),
        )


def test_alias_mapping_cannot_be_swapped():
    prepared = prepare_handover(input=make_input())
    other = make_input().retrieval.evidence.shift_records[0].reference
    prepared.aliases._alias_to_source["SRC_001"] = other
    with pytest.raises(InboundValidationError):
        resolve_handover(prepared=prepared, output=run_fake(prepared))


def test_caller_mutation_does_not_change_prepared_evidence():
    value = make_input()
    prepared = prepare_handover(input=value)
    value.retrieval.evidence.shift_records[0].clinical_data["volume_ml"] = 999
    assert prepared.input.retrieval.evidence.shift_records[0].clinical_data["volume_ml"] == 150
    resolve_handover(prepared=prepared, output=run_fake(prepared))


@pytest.mark.parametrize(
    "kind,source,data,precision",
    [
        (
            "mobility",
            "mobility_observations",
            {"activity": "Walking", "assistance_given": "One staff"},
            "timestamp",
        ),
        ("fall", "falls_incidents", {"action_taken": "Review requested", "witnessed": False}, "timestamp"),
        ("wound", "wound_records", {"body_location": "Left shin"}, "date"),
        ("mobility", "mobility_observations", {"activity": "Walking"}, "unknown"),
    ],
)
def test_source_fixtures_through_all_stages(kind, source, data, precision):
    from datetime import date

    from intelligence.handover.evidence import assemble_shift_evidence

    value = make_input()
    record = value.retrieval.evidence.shift_records[0]
    record = record.model_copy(
        update={
            "kind": kind,
            "reference": record.reference.model_copy(update={"source_type": source}),
            "clinical_data": data,
            "time_precision": precision,
            "time_basis": "unknown" if precision == "unknown" else "effective",
            "effective_at": record.effective_at if precision == "timestamp" else None,
            "source_date": date(2026, 10, 4) if precision == "date" else None,
        }
    )
    evidence = assemble_shift_evidence(
        (record,),
        context=value.execution_context,
        expected_resident_id=value.resident_id,
        period=value.period,
        care_home_timezone=value.care_home_timezone,
    )
    value = replace_evidence(value, evidence).model_copy(
        update={"metrics": calculate_handover_metrics(evidence, retrieval_complete=False)}
    )
    policy = ReviewedTextPolicy({v: v for v in data.values() if isinstance(v, str)})
    prepared = prepare_handover(input=value, text_policy=policy)
    output = run_fake(prepared)
    result = resolve_handover(prepared=prepared, output=output)
    assert result.sections[0].claims[0].sources == (record.reference,)
    assert set(evidence.warnings).issubset(result.warnings)
    if precision != "timestamp":
        assert output.claims[0].context != "shift"
        wrong = output.model_copy(
            update={"claims": (output.claims[0].model_copy(update={"context": "shift"}),)}
        )
        with pytest.raises(InboundValidationError):
            resolve_handover(prepared=prepared, output=wrong)


def test_two_requests_keep_independent_maps():
    async def run():
        async def one():
            prepared = prepare_handover(input=make_input())
            output = await FakeHandoverProvider().generate(prepared.payload)
            return resolve_handover(prepared=prepared, output=output)

        return await asyncio.gather(one(), one())

    first, second = asyncio.run(run())
    assert first.sections[0].claims[0].sources != second.sections[0].claims[0].sources


def test_oversized_text_rejected_before_dispatch():
    text = "x" * 2100
    with pytest.raises(OutboundValidationError):
        prepare_handover(input=with_notes(text), text_policy=ReviewedTextPolicy({text: text}))
