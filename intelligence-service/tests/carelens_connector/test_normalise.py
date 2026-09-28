from datetime import date
from uuid import UUID

import pytest

from intelligence.connectors.carelens import ObservationResponse
from intelligence.connectors.normalise import (
    EvidenceNormalisationError,
    normalise_observation,
)
from intelligence.core.contracts import ExecutionContext


TENANT_ID = UUID("10000000-0000-0000-0000-000000000001")
RESIDENT_ID = UUID("30000000-0000-0000-0000-000000000001")
OTHER_RESIDENT_ID = UUID("30000000-0000-0000-0000-000000000002")


def context() -> ExecutionContext:
    return ExecutionContext(
        tenant_id=TENANT_ID,
        service_identity="synthetic-test-service",
        trigger="scheduled",
        authorised_resident_ids=frozenset({RESIDENT_ID}),
        permissions=frozenset({"evidence:read"}),
    )


def observation(**changes) -> ObservationResponse:
    data = {
        "id": "40000000-0000-0000-0000-000000000001",
        "resident_id": str(RESIDENT_ID),
        "type": "fluid_intake",
        "value": {
            "volume_ml": 150,
            "ml": 150,
            "notes": "Synthetic note",
        },
        "recorded_at": "2026-09-08T08:00:00+01:00",
        "recorded_by": None,
        "is_implausible": False,
        "source_type": "fluid_intake_records",
        "time_precision": "timestamp",
        "source_date": None,
    }
    data.update(changes)
    return ObservationResponse.model_validate(data)


def test_normalises_fluid_without_losing_source_data():
    raw = observation()

    result = normalise_observation(
        raw,
        context=context(),
        expected_resident_id=RESIDENT_ID,
    )

    assert result is not None
    assert result.resident_id == RESIDENT_ID
    assert result.reference.source_id == raw.id
    assert result.kind == "fluid_intake"
    assert result.clinical_data == raw.value

    assert result.effective_at == raw.recorded_at
    assert result.recorded_at is None
    assert result.time_precision == "timestamp"

    # Extraction/calculation is a later step.
    assert result.consumed_ml is None

    raw.value["volume_ml"] = 999
    assert result.clinical_data["volume_ml"] == 150


def test_rejects_wrong_resident():
    with pytest.raises(
        EvidenceNormalisationError,
        match="Unexpected resident",
    ):
        normalise_observation(
            observation(resident_id=str(OTHER_RESIDENT_ID)),
            context=context(),
            expected_resident_id=RESIDENT_ID,
        )


def test_excludes_native_observations():
    result = normalise_observation(
        observation(source_type="observations"),
        context=context(),
        expected_resident_id=RESIDENT_ID,
    )

    assert result is None


def test_preserves_date_only_sleep():
    result = normalise_observation(
        observation(
            source_type="sleep_records",
            type="sleep",
            value={"hours": 6},
            time_precision="date",
            source_date="2026-09-08",
            recorded_at="2026-09-08T00:00:00+01:00",
        ),
        context=context(),
        expected_resident_id=RESIDENT_ID,
    )

    assert result is not None
    assert result.source_date == date(2026, 9, 8)
    assert result.effective_at is None
    assert result.recorded_at is None
    assert result.time_precision == "date"


def test_fingerprint_changes_when_content_changes():
    original = normalise_observation(
        observation(),
        context=context(),
        expected_resident_id=RESIDENT_ID,
    )
    corrected = normalise_observation(
        observation(value={"volume_ml": 120, "ml": 120}),
        context=context(),
        expected_resident_id=RESIDENT_ID,
    )

    assert original is not None
    assert corrected is not None
    assert original.reference.source_id == corrected.reference.source_id
    assert (
        original.reference.fingerprint
        != corrected.reference.fingerprint
    )

def test_rejects_resident_outside_authorised_scope():
    restricted_context = context().model_copy(
        update={"authorised_resident_ids": frozenset()}
    )

    with pytest.raises(
        EvidenceNormalisationError,
        match="outside the authorised scope",
    ):
        normalise_observation(
            observation(),
            context=restricted_context,
            expected_resident_id=RESIDENT_ID,
        )

def test_rejects_unknown_source():
    with pytest.raises(
        EvidenceNormalisationError,
        match="Unsupported observation source",
    ):
        normalise_observation(
            observation(source_type="unexpected_table"),
            context=context(),
            expected_resident_id=RESIDENT_ID,
        )


def test_rejects_source_type_mismatch():
    with pytest.raises(
        EvidenceNormalisationError,
        match="does not match source",
    ):
        normalise_observation(
            observation(type="wound"),
            context=context(),
            expected_resident_id=RESIDENT_ID,
        )

@pytest.mark.parametrize(
    "source_date",
    [None, "not-a-date", "2026-02-30"],
)
def test_rejects_missing_or_invalid_source_date(source_date):
    with pytest.raises(EvidenceNormalisationError):
        normalise_observation(
            observation(
                source_type="sleep_records",
                type="sleep",
                value={"hours": 6},
                time_precision="date",
                source_date=source_date,
            ),
            context=context(),
            expected_resident_id=RESIDENT_ID,
        )

def test_rejects_timestamp_source_with_date_precision():
    with pytest.raises(
        EvidenceNormalisationError,
        match="unexpected precision",
    ):
        normalise_observation(
            observation(
                time_precision="date",
                source_date="2026-09-08",
            ),
            context=context(),
            expected_resident_id=RESIDENT_ID,
        )


def test_rejects_date_source_with_timestamp_precision():
    with pytest.raises(
        EvidenceNormalisationError,
        match="unexpected precision",
    ):
        normalise_observation(
            observation(
                source_type="sleep_records",
                type="sleep",
                value={"hours": 6},
                time_precision="timestamp",
                source_date="2026-09-08",
            ),
            context=context(),
            expected_resident_id=RESIDENT_ID,
        )


def test_rejects_timestamp_source_with_source_date():
    with pytest.raises(
        EvidenceNormalisationError,
        match="date-only metadata",
    ):
        normalise_observation(
            observation(source_date="2026-09-08"),
            context=context(),
            expected_resident_id=RESIDENT_ID,
        )

def test_fingerprint_is_stable_across_dictionary_order():
    first = normalise_observation(
        observation(
            value={"volume_ml": 150, "ml": 150}
        ),
        context=context(),
        expected_resident_id=RESIDENT_ID,
    )

    second = normalise_observation(
        observation(
            value={"ml": 150, "volume_ml": 150}
        ),
        context=context(),
        expected_resident_id=RESIDENT_ID,
    )

    assert first is not None
    assert second is not None
    assert (
        first.reference.fingerprint
        == second.reference.fingerprint
    )