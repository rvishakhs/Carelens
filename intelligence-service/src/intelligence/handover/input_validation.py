"""Consistency checks before rendering or provider dispatch.

The workflow must establish current authorisation separately. This validator
checks the supplied scope; it does not contact CareLens or grant permissions.
"""

from datetime import UTC
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from intelligence.handover.contracts import HandoverAgentInput
from intelligence.handover.evidence import (
    EvidenceValidationError,
    assemble_shift_evidence,
)
from intelligence.handover.metrics import MetricsInputError, calculate_handover_metrics


class InternalInputValidationError(ValueError):
    """Internal handover input failed consistency checks; messages omit data."""


def validate_internal_input(input: HandoverAgentInput) -> None:
    context = input.execution_context
    retrieval = input.retrieval
    evidence = retrieval.evidence

    if input.resident_id not in context.authorised_resident_ids:
        raise InternalInputValidationError("Resident is outside the supplied scope")
    if "handover:generate" not in context.permissions:
        raise InternalInputValidationError("Handover generation permission is missing")

    try:
        ZoneInfo(input.care_home_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise InternalInputValidationError("Invalid care-home timezone") from None

    start = input.period.start.astimezone(UTC)
    end = input.period.end.astimezone(UTC)
    retrieved_at = retrieval.retrieved_at.astimezone(UTC)
    if start >= end:
        raise InternalInputValidationError("Invalid handover period")
    if end > retrieved_at:
        raise InternalInputValidationError("Retrieval predates the end of the period")
    if (
        retrieval.evidence_cutoff is not None
        and retrieval.evidence_cutoff.astimezone(UTC) > retrieved_at
    ):
        raise InternalInputValidationError("Evidence cutoff follows retrieval")
    if evidence.outside_shift_count < 0:
        raise InternalInputValidationError("Invalid excluded-record count")

    # Reuse the assembler's tenant/resident, identity and DST-aware time rules.
    # Duplicate logical sources are rejected even if versions/fingerprints differ.
    records = (
        *evidence.shift_records,
        *evidence.date_context,
        *evidence.unknown_time_records,
    )
    try:
        assembled = assemble_shift_evidence(
            records,
            context=context,
            expected_resident_id=input.resident_id,
            period=input.period,
            care_home_timezone=input.care_home_timezone,
        )
    except EvidenceValidationError:
        raise InternalInputValidationError("Evidence scope or source identity is invalid") from None

    if (
        assembled.outside_shift_count
        or assembled.shift_records != evidence.shift_records
        or assembled.date_context != evidence.date_context
        or assembled.unknown_time_records != evidence.unknown_time_records
    ):
        raise InternalInputValidationError("Evidence is assigned to an invalid time group")
    if not set(assembled.warnings).issubset(evidence.warnings):
        raise InternalInputValidationError("Required evidence warnings are missing")

    if input.metrics.retrieval_complete != retrieval.coverage_complete:
        raise InternalInputValidationError("Metric and retrieval coverage disagree")

    # Recalculation verifies all totals, portions, counts, warnings and complete
    # SourceRefs (including fingerprints), rather than only alias membership.
    try:
        expected_metrics = calculate_handover_metrics(
            evidence,
            retrieval_complete=retrieval.coverage_complete,
        )
    except MetricsInputError:
        raise InternalInputValidationError("Evidence cannot support the supplied metrics") from None
    if input.metrics != expected_metrics:
        raise InternalInputValidationError("Metrics do not match the supplied evidence")
