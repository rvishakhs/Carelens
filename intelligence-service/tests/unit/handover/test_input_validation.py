from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from intelligence.handover.evidence import assemble_shift_evidence
from intelligence.handover.input_validation import (
    InternalInputValidationError,
    validate_internal_input,
)
from intelligence.handover.metrics import calculate_handover_metrics
from tests.support.handover import make_input, replace_evidence


def test_valid_input_and_start_boundary():
    validate_internal_input(make_input())


@pytest.mark.parametrize("field", ["tenant_id", "resident_id"])
def test_wrong_record_scope(field):
    value = make_input()
    evidence = value.retrieval.evidence
    record = evidence.shift_records[0].model_copy(update={field: uuid4()})
    with pytest.raises(InternalInputValidationError):
        validate_internal_input(
            replace_evidence(value, evidence.model_copy(update={"shift_records": (record,)}))
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"permissions": frozenset()},
        {"authorised_resident_ids": frozenset()},
    ],
)
def test_scope_denial(changes):
    value = make_input()
    with pytest.raises(InternalInputValidationError):
        validate_internal_input(
            value.model_copy(
                update={
                    "execution_context": value.execution_context.model_copy(update=changes),
                }
            )
        )


@pytest.mark.parametrize("variant", ["end", "duplicate", "revision", "wrong_group"])
def test_invalid_evidence_assignment(variant):
    value = make_input()
    evidence = value.retrieval.evidence
    record = evidence.shift_records[0]
    if variant == "end":
        evidence = evidence.model_copy(
            update={"shift_records": (record.model_copy(update={"effective_at": value.period.end}),)}
        )
    elif variant in {"duplicate", "revision"}:
        other = (
            record
            if variant == "duplicate"
            else record.model_copy(
                update={"reference": record.reference.model_copy(update={"fingerprint": "corrected"})}
            )
        )
        evidence = evidence.model_copy(update={"shift_records": (record, other)})
    else:
        evidence = evidence.model_copy(update={"shift_records": (), "date_context": (record,)})
    with pytest.raises(InternalInputValidationError):
        validate_internal_input(replace_evidence(value, evidence))


@pytest.mark.parametrize("variant", ["value", "source", "coverage"])
def test_metric_tampering(variant):
    value = make_input()
    metrics = value.metrics
    if variant == "coverage":
        metrics = metrics.model_copy(update={"retrieval_complete": True})
    else:
        change = (
            {"known_subtotal": Decimal("999")}
            if variant == "value"
            else {"sources": (metrics.consumed.sources[0].model_copy(update={"source_id": uuid4()}),)}
        )
        metrics = metrics.model_copy(update={"consumed": metrics.consumed.model_copy(update=change)})
    with pytest.raises(InternalInputValidationError):
        validate_internal_input(value.model_copy(update={"metrics": metrics}))


def test_date_context_preserves_warning_and_exclusion_from_totals():
    value = make_input()
    record = value.retrieval.evidence.shift_records[0].model_copy(
        update={
            "effective_at": None,
            "time_precision": "date",
            "source_date": date(2026, 10, 4),
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
        update={
            "metrics": calculate_handover_metrics(evidence, retrieval_complete=False),
        }
    )
    validate_internal_input(value)
    with pytest.raises(InternalInputValidationError):
        validate_internal_input(replace_evidence(value, evidence.model_copy(update={"warnings": ()})))


def test_invalid_timezone_is_controlled():
    with pytest.raises(InternalInputValidationError):
        validate_internal_input(make_input().model_copy(update={"care_home_timezone": "Invalid/Zone"}))


def test_retrieval_before_period_end():
    value = make_input()
    with pytest.raises(InternalInputValidationError):
        validate_internal_input(
            value.model_copy(
                update={"retrieval": value.retrieval.model_copy(update={"retrieved_at": value.period.start})}
            )
        )
