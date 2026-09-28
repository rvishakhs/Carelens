import hashlib
import json
from copy import deepcopy
from datetime import date
from uuid import UUID

from intelligence.connectors.carelens import ObservationResponse
from intelligence.core.contracts import (
    Evidence,
    ExecutionContext,
    SourceRef,
)


SOURCE_KINDS = {
    "fluid_intake_records": "fluid_intake",
    "food_intake_records": "meal",
    "weight_records": "weight",
    "vital_signs_records": "vitals",
    "mobility_observations": "mobility",
    "continence_records": "continence",
    "wellbeing_records": "wellbeing",
    "behaviour_records": "behaviour",
    "communication_logs": "communication",
    "sleep_records": "sleep",
    "pain_assessments": "pain",
    "falls_incidents": "fall",
    "incidents": "incident",
    "wound_records": "wound",
}

EXCLUDED_SOURCES = frozenset({"observations"})

DATE_ONLY_SOURCES = frozenset({
    "sleep_records",
    "wound_records",
})


class EvidenceNormalisationError(ValueError):
    """A source record cannot be safely converted to evidence."""

def observation_fingerprint(
        record: ObservationResponse,
) -> str:
    try:
        canonical = json.dumps(
            record.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        raise EvidenceNormalisationError(
            "Observation cannot be fingerprinted"
        ) from None

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

def validate_observation_source(
    record: ObservationResponse,
    *,
    context: ExecutionContext,
    expected_resident_id: UUID,
) -> str | None:
    if expected_resident_id not in context.authorised_resident_ids:
        raise EvidenceNormalisationError(
            "Resident is outside the authorised scope"
        )

    if record.resident_id != expected_resident_id:
        raise EvidenceNormalisationError(
            "Unexpected resident in observation"
        )

    if record.source_type in EXCLUDED_SOURCES:
        return None

    expected_kind = SOURCE_KINDS.get(record.source_type)

    if expected_kind is None:
        raise EvidenceNormalisationError(
            "Unsupported observation source"
        )

    if record.type != expected_kind:
        raise EvidenceNormalisationError(
            "Observation type does not match source"
        )

    return expected_kind

def normalise_observation(
    record: ObservationResponse,
    *,
    context: ExecutionContext,
    expected_resident_id: UUID,
) -> Evidence | None:
    kind = validate_observation_source(
        record,
        context=context,
        expected_resident_id=expected_resident_id,
    )

    if kind is None:
        # Deliberately excluded from this pilot.
        return None

    reference = SourceRef(
        source_system="Carelens_connector",
        source_type=record.source_type,
        source_id=record.id,
        version="unversioned",
        fingerprint=observation_fingerprint(record),
    )

    if record.source_type in DATE_ONLY_SOURCES:
        if record.time_precision != "date":
            raise EvidenceNormalisationError(
                "Date-only source has unexpected precision"
            )

        if record.source_date is None:
            raise EvidenceNormalisationError(
                "Date-only source is missing its date"
            )

        try:
            source_date = date.fromisoformat(record.source_date)
        except ValueError:
            raise EvidenceNormalisationError(
                "Date-only source has an invalid date"
            ) from None

        return Evidence(
            tenant_id=context.tenant_id,
            resident_id=expected_resident_id,
            reference=reference,
            is_implausible=record.is_implausible,
            effective_at=None,
            recorded_at=None,
            source_date=source_date,
            time_basis="effective",
            time_precision="date",
            kind=kind,
            clinical_data=deepcopy(record.value),
        )

    if record.time_precision != "timestamp":
        raise EvidenceNormalisationError(
            "Timestamp source has unexpected precision"
        )

    if record.source_date is not None:
        raise EvidenceNormalisationError(
            "Timestamp source contains date-only metadata"
        )

    return Evidence(
        tenant_id=context.tenant_id,
        resident_id=expected_resident_id,
        reference=reference,
        is_implausible=record.is_implausible,

        # CareLens uses this response field for projected clinical time.
        effective_at=record.recorded_at,

        # The actual entry timestamp is not supplied separately.
        recorded_at=None,

        source_date=None,
        time_basis="effective",
        time_precision="timestamp",
        kind=kind,
        clinical_data=deepcopy(record.value),
    )