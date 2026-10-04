from datetime import date, datetime
from uuid import UUID

import pytest

from intelligence.core.contracts import (
    Evidence,
    ExecutionContext,
    Period,
    SourceRef,
)
from intelligence.handover.evidence import (
    EvidenceValidationError,
    assemble_shift_evidence,
)

TENANT_ID = UUID("10000000-0000-0000-0000-000000000001")
RESIDENT_ID = UUID("30000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("90000000-0000-0000-0000-000000000001")


def context():
    return ExecutionContext(
        tenant_id=TENANT_ID,
        service_identity="synthetic-test-service",
        trigger="scheduled",
        authorised_resident_ids=frozenset({RESIDENT_ID}),
        permissions=frozenset({"evidence:read"}),
    )


def timestamp_record(number, timestamp):
    return Evidence(
        tenant_id=TENANT_ID,
        resident_id=RESIDENT_ID,
        reference=SourceRef(
            source_system="Carelens_connector",
            source_type="fluid_intake_records",
            source_id=UUID(f"40000000-0000-0000-0000-{number:012d}"),
            version="unversioned",
        ),
        effective_at=datetime.fromisoformat(timestamp),
        time_basis="effective",
        time_precision="timestamp",
        kind="fluid_intake",
        clinical_data={"volume_ml": 150},
    )


def assemble(records, **changes):
    arguments = {
        "context": context(),
        "expected_resident_id": RESIDENT_ID,
        "period": Period(
            start="2026-09-08T07:00:00+01:00",
            end="2026-09-08T19:00:00+01:00",
        ),
        "care_home_timezone": "Europe/London",
    }
    arguments.update(changes)

    return assemble_shift_evidence(
        tuple(records),
        **arguments,
    )


def test_shift_start_included_and_end_excluded():
    records = [
        timestamp_record(1, "2026-09-08T06:59:00+01:00"),
        timestamp_record(2, "2026-09-08T07:00:00+01:00"),
        timestamp_record(3, "2026-09-08T18:59:00+01:00"),
        timestamp_record(4, "2026-09-08T19:00:00+01:00"),
    ]

    result = assemble(records)

    assert result.shift_records == tuple(records[1:3])
    assert result.outside_shift_count == 2


def test_rejects_duplicate_source_identity():
    record = timestamp_record(1, "2026-09-08T08:00:00+01:00")

    with pytest.raises(
        EvidenceValidationError,
        match="Duplicate source identity",
    ):
        assemble([record, record])


@pytest.mark.parametrize(
    "changes",
    [
        {"tenant_id": OTHER_ID},
        {"resident_id": OTHER_ID},
    ],
)
def test_rejects_wrong_scope(changes):
    record = timestamp_record(1, "2026-09-08T08:00:00+01:00").model_copy(update=changes)

    with pytest.raises(EvidenceValidationError):
        assemble([record])


def test_date_only_record_is_context_not_shift_event():
    record = Evidence(
        tenant_id=TENANT_ID,
        resident_id=RESIDENT_ID,
        reference=SourceRef(
            source_system="Carelens_connector",
            source_type="wound_records",
            source_id=OTHER_ID,
            version="unversioned",
        ),
        source_date=date(2026, 9, 8),
        time_basis="effective",
        time_precision="date",
        kind="wound",
        clinical_data={"location": "left shin"},
    )

    result = assemble([record])

    assert result.shift_records == ()
    assert result.date_context == (record,)
    assert result.warnings


def test_late_entry_uses_effective_time():
    record = timestamp_record(1, "2026-09-08T18:50:00+01:00").model_copy(
        update={
            "recorded_at": datetime.fromisoformat("2026-09-08T19:10:00+01:00"),
        }
    )

    result = assemble([record])

    assert result.shift_records == (record,)
