"""Synthetic handover builders shared by unit tests."""

from datetime import UTC, datetime
from uuid import uuid4

from intelligence.core.contracts import Evidence, ExecutionContext, Period, SourceRef
from intelligence.handover.contracts import HandoverAgentInput, HandoverRetrieval
from intelligence.handover.evidence import assemble_shift_evidence
from intelligence.handover.metrics import calculate_handover_metrics


def make_input():
    resident = uuid4()
    context = ExecutionContext(
        tenant_id=uuid4(),
        service_identity="test-worker",
        trigger="scheduled",
        authorised_resident_ids=frozenset({resident}),
        permissions=frozenset({"handover:generate"}),
    )
    period = Period(
        start=datetime(2026, 10, 4, 6, tzinfo=UTC),
        end=datetime(2026, 10, 4, 18, tzinfo=UTC),
    )
    record = Evidence(
        tenant_id=context.tenant_id,
        resident_id=resident,
        reference=SourceRef(
            source_type="fluid_intake_records",
            source_id=uuid4(),
            version="unversioned",
            fingerprint="original",
        ),
        kind="fluid_intake",
        clinical_data={"volume_ml": 150},
        effective_at=period.start,
        time_basis="effective",
        time_precision="timestamp",
    )
    evidence = assemble_shift_evidence(
        (record,),
        context=context,
        expected_resident_id=resident,
        period=period,
        care_home_timezone="Europe/London",
    )
    return HandoverAgentInput(
        execution_context=context,
        job_id=uuid4(),
        resident_id=resident,
        period=period,
        care_home_timezone="Europe/London",
        retrieval=HandoverRetrieval(evidence=evidence, retrieved_at=period.end, coverage_complete=False),
        metrics=calculate_handover_metrics(evidence, retrieval_complete=False),
    )


def replace_evidence(value, evidence):
    return value.model_copy(
        update={
            "retrieval": value.retrieval.model_copy(update={"evidence": evidence}),
        }
    )


def with_notes(text):
    value = make_input()
    evidence = value.retrieval.evidence
    record = evidence.shift_records[0].model_copy(update={"clinical_data": {"volume_ml": 150, "notes": text}})
    evidence = evidence.model_copy(update={"shift_records": (record,)})
    return replace_evidence(value, evidence).model_copy(
        update={"metrics": calculate_handover_metrics(evidence, retrieval_complete=False)}
    )
