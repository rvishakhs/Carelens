from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from intelligence.core.contracts import (
    Contract,
    Evidence,
    ExecutionContext,
    Period,
)


class EvidenceValidationError(ValueError):
    """Evidence cannot safely be assembled for this handover."""


class ShiftEvidence(Contract):
    shift_records: tuple[Evidence, ...]
    date_context: tuple[Evidence, ...]
    unknown_time_records: tuple[Evidence, ...]

    outside_shift_count: int
    warnings: tuple[str, ...]

def assemble_shift_evidence(
    records: tuple[Evidence, ...],
    *,
    context: ExecutionContext,
    expected_resident_id: UUID,
    period: Period,
    care_home_timezone: str,
) -> ShiftEvidence:
    if expected_resident_id not in context.authorised_resident_ids:
        raise EvidenceValidationError(
            "Resident is outside the authorised scope"
        )

    zone = ZoneInfo(care_home_timezone)

    # Compare actual instants, including across daylight-saving changes.
    start = period.start.astimezone(UTC)
    end = period.end.astimezone(UTC)

    shift_records: list[Evidence] = []
    date_context: list[Evidence] = []
    unknown_time_records: list[Evidence] = []
    outside_shift_count = 0

    seen: set[tuple[str, UUID, str, UUID]] = set()

    for record in records:
        if record.tenant_id != context.tenant_id:
            raise EvidenceValidationError(
                "Unexpected tenant in evidence"
            )

        if record.resident_id != expected_resident_id:
            raise EvidenceValidationError(
                "Unexpected resident in evidence"
            )

        identity = (
            record.reference.source_system,
            record.tenant_id,
            record.reference.source_type,
            record.reference.source_id,
        )

        if identity in seen:
            raise EvidenceValidationError(
                "Duplicate source identity in evidence"
            )

        seen.add(identity)

        if record.time_precision == "date":
            if record.source_date is None:
                raise EvidenceValidationError(
                    "Date-only evidence is missing its date"
                )

            day_start = datetime.combine(
                record.source_date,
                time.min,
                tzinfo=zone,
            ).astimezone(UTC)

            day_end = datetime.combine(
                record.source_date + timedelta(days=1),
                time.min,
                tzinfo=zone,
            ).astimezone(UTC)

            # Half-open intervals overlap when each starts before
            # the other ends.
            if day_start < end and start < day_end:
                date_context.append(record)
            else:
                outside_shift_count += 1

            continue

        if record.time_precision == "unknown":
            unknown_time_records.append(record)
            continue

        if record.time_basis == "effective":
            timestamp = record.effective_at
        elif record.time_basis == "recorded":
            timestamp = record.recorded_at
        else:
            raise EvidenceValidationError(
                "Timestamp evidence has no usable time basis"
            )

        if timestamp is None:
            raise EvidenceValidationError(
                "Timestamp evidence is missing its timestamp"
            )

        instant = timestamp.astimezone(UTC)

        if start <= instant < end:
            shift_records.append(record)
        else:
            outside_shift_count += 1

    warnings: list[str] = []

    if date_context:
        warnings.append(
            "Date-only records overlap the shift's calendar dates; "
            "their exact shift attribution is unknown."
        )

    if unknown_time_records:
        warnings.append(
            "Some records have unknown times and cannot be "
            "assigned to this shift."
        )

    return ShiftEvidence(
        shift_records=tuple(shift_records),
        date_context=tuple(date_context),
        unknown_time_records=tuple(unknown_time_records),
        outside_shift_count=outside_shift_count,
        warnings=tuple(warnings),
    )
