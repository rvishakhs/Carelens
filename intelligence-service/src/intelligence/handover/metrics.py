"""Pure, source-backed calculations over already scoped/assembled shift evidence.

No network, model, database writes or inference from narrative text. See
``docs/handover-metrics.md`` for the explicit linked-drink input contract.
"""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from intelligence.core.contracts import Contract, Evidence, SourceRef
from intelligence.handover.evidence import ShiftEvidence


class MetricTotal(Contract):
    value: Decimal | None
    known_subtotal: Decimal
    status: Literal["complete", "partial", "no_records", "ambiguous"]
    sources: tuple[SourceRef, ...]


class FluidPortion(Contract):
    source: SourceRef
    at: datetime
    time_basis: str
    offer_id: str | None
    consumed_ml: Decimal | None
    offered_ml: Decimal | None
    mode: str
    # Delta is populated only after the entire linked group is validated.
    consumption_delta_ml: Decimal | None = None


class MealPortion(Contract):
    source: SourceRef
    at: datetime
    meal: str | None
    percentage_eaten: Decimal | None


class RecordCount(Contract):
    kind: str
    count: int
    sources: tuple[SourceRef, ...]


class HandoverMetrics(Contract):
    consumed: MetricTotal
    offered: MetricTotal
    fluids: tuple[FluidPortion, ...]
    meals: tuple[MealPortion, ...]
    record_counts: tuple[RecordCount, ...]
    retrieval_complete: bool
    warnings: tuple[str, ...]


class MetricsInputError(ValueError):
    pass


def _number(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise MetricsInputError("Expected a finite non-negative number")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise MetricsInputError("Invalid numeric field") from None
    if not number.is_finite() or number < 0:
        raise MetricsInputError("Expected a finite non-negative number")
    return number


def _aliases(*values: object) -> Decimal | None:
    numbers = {_number(value) for value in values if value is not None}
    if len(numbers) > 1:
        raise MetricsInputError("Conflicting aliases for the same measurement")
    return next(iter(numbers), None)


def _time(record: Evidence) -> datetime:
    timestamp = record.effective_at if record.time_basis == "effective" else record.recorded_at
    if record.time_precision != "timestamp" or timestamp is None:
        raise MetricsInputError("Shift records must have an assigned timestamp")
    return timestamp.astimezone(UTC)


def _total(
    values: list[Decimal],
    sources: list[SourceRef],
    *,
    complete: bool,
    missing: bool,
    ambiguous: bool,
    present: bool,
) -> MetricTotal:
    subtotal = sum(values, Decimal(0))
    status: Literal["complete", "partial", "no_records", "ambiguous"]
    if ambiguous:
        status = "ambiguous"
    elif not complete or missing:
        status = "partial"
    elif not present:
        status = "no_records"
    else:
        status = "complete"
    return MetricTotal(
        value=subtotal if status == "complete" else None,
        known_subtotal=subtotal,
        status=status,
        sources=tuple(sources),
    )


def calculate_handover_metrics(evidence: ShiftEvidence, *, retrieval_complete: bool) -> HandoverMetrics:
    """Return exact recorded metrics; completeness must be supplied by retrieval.

    Does not assert all care performed was recorded. Unknown/date-only context is
    excluded from exact totals. Missing or ambiguous amounts never become zero.
    """
    all_records = (*evidence.shift_records, *evidence.date_context, *evidence.unknown_time_records)
    if len({(r.tenant_id, r.resident_id) for r in all_records}) > 1:
        raise MetricsInputError("Mixed resident or tenant evidence")
    identities = [
        (r.reference.source_system, r.reference.source_type, r.reference.source_id) for r in all_records
    ]
    if len(set(identities)) != len(identities):
        raise MetricsInputError("Duplicate source identity; resolve revisions before calculating")

    warnings = list(evidence.warnings)
    if not retrieval_complete:
        warnings.append("Retrieval is incomplete; full-period totals are unavailable.")
    uncertain_fluid = any(
        r.kind in {"fluid", "fluid_intake"} for r in (*evidence.date_context, *evidence.unknown_time_records)
    )
    if evidence.date_context or evidence.unknown_time_records:
        warnings.append("Date-only/unknown-time context excluded from exact shift metrics and counts.")
    fluids: list[FluidPortion] = []
    meals: list[MealPortion] = []
    counts: dict[str, list[SourceRef]] = defaultdict(list)
    baseline: dict[SourceRef, Decimal | None] = {}
    for record in sorted(
        evidence.shift_records, key=lambda r: (_time(r), r.reference.source_type, str(r.reference.source_id))
    ):
        counts[record.kind].append(record.reference)
        data = record.clinical_data
        if record.kind in {"fluid", "fluid_intake"}:
            offer_id = data.get("offer_id")
            if offer_id is not None and (not isinstance(offer_id, str) or not offer_id.strip()):
                raise MetricsInputError("offer_id must be a non-empty string")
            # Unlinked historical intake rows represent recorded portions. Linked
            # rows require an explicit mode; neither prose nor timing can supply it.
            mode = data.get("consumption_mode", "unknown" if offer_id else "incremental")
            if mode not in {"incremental", "cumulative", "unknown"}:
                raise MetricsInputError("Unsupported consumption mode")
            consumed = _aliases(
                record.consumed_ml, data.get("consumed_ml"), data.get("volume_ml"), data.get("ml")
            )
            offered = _aliases(record.offered_ml, data.get("offered_ml"))
            fluids.append(
                FluidPortion(
                    source=record.reference,
                    at=_time(record),
                    time_basis=record.time_basis,
                    offer_id=offer_id,
                    consumed_ml=consumed,
                    offered_ml=offered,
                    mode=str(mode),
                )
            )
            baseline[record.reference] = _number(data.get("opening_consumed_ml"))
        elif record.kind == "meal":
            fraction = _number(data.get("fraction_eaten"))
            percentage = _aliases(
                data.get("percentage_eaten"), fraction * 100 if fraction is not None else None
            )
            if percentage is not None and percentage > 100:
                raise MetricsInputError("Meal percentage must be between 0 and 100")
            meal = data.get("meal_type", data.get("meal"))
            if meal is not None and not isinstance(meal, str):
                raise MetricsInputError("Meal label must be text")
            meals.append(
                MealPortion(source=record.reference, at=_time(record), meal=meal, percentage_eaten=percentage)
            )
            if percentage is None:
                warnings.append("A meal record has no consumed percentage.")

    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, row in enumerate(fluids):
        groups[("offer", row.offer_id) if row.offer_id else ("record", str(i))].append(i)
    consumed_values: list[Decimal] = []
    offered_values: list[Decimal] = []
    consumed_sources: list[SourceRef] = []
    offered_sources: list[SourceRef] = []
    consumed_missing = offered_missing = uncertain_fluid
    consumed_ambiguous = offered_ambiguous = False
    for indexes in groups.values():
        rows = [fluids[i] for i in indexes]
        offers = {r.offered_ml for r in rows if r.offered_ml is not None}
        if len(offers) > 1:
            offered_ambiguous = True
            warnings.append("Conflicting offered amounts for one offer; offered total withheld.")
        elif offers:
            offered_values.append(next(iter(offers)))
            offered_sources.extend(r.source for r in rows if r.offered_ml is not None)
        else:
            offered_missing = True
        modes = {r.mode for r in rows}
        ambiguous = len(modes) != 1 or "unknown" in modes
        deltas: list[Decimal] = []
        if modes == {"cumulative"}:
            opening = baseline[rows[0].source]
            # Require an explicit shift-opening baseline (zero for a new offer).
            # Same-time cumulative readings cannot be reliably ordered.
            ambiguous |= (
                rows[0].offer_id is None
                or opening is None
                or len({r.at for r in rows}) != len(rows)
                or any(baseline[r.source] not in {None, opening} for r in rows)
            )
            previous = opening
            for row in rows:
                if row.consumed_ml is None:
                    consumed_missing = True
                    break
                if previous is None or row.consumed_ml < previous:
                    ambiguous = True
                    break
                deltas.append(row.consumed_ml - previous)
                previous = row.consumed_ml
        elif modes == {"incremental"}:
            if any(baseline[r.source] is not None for r in rows):
                ambiguous = True
            deltas = [r.consumed_ml for r in rows if r.consumed_ml is not None]
        if ambiguous:
            consumed_ambiguous = True
            warnings.append(
                "Fluid consumption is ambiguous; require offer linkage, mode and cumulative baseline."
            )
            continue
        if len(deltas) != len(rows):
            consumed_missing = True
            warnings.append("A fluid amount is missing; complete consumed total is unavailable.")
            continue
        # A known linked offer bounds total consumption, including the opening baseline.
        lifetime = sum(deltas, Decimal(0)) + (baseline[rows[0].source] or 0)
        if rows[0].offer_id and len(offers) == 1 and lifetime > next(iter(offers)):
            consumed_ambiguous = True
            warnings.append("Linked consumption exceeds the recorded offer; reconcile before totalling.")
            continue
        consumed_values.extend(deltas)
        consumed_sources.extend(r.source for r in rows)
        for index, delta in zip(indexes, deltas, strict=True):
            fluids[index] = fluids[index].model_copy(update={"consumption_delta_ml": delta})
    if offered_missing:
        warnings.append("Offered amounts are not fully recorded; consumed amounts do not imply offers.")

    return HandoverMetrics(
        consumed=_total(
            consumed_values,
            consumed_sources,
            complete=retrieval_complete,
            missing=consumed_missing,
            ambiguous=consumed_ambiguous,
            present=bool(fluids),
        ),
        offered=_total(
            offered_values,
            offered_sources,
            complete=retrieval_complete,
            missing=offered_missing,
            ambiguous=offered_ambiguous,
            present=bool(fluids),
        ),
        fluids=tuple(fluids),
        meals=tuple(meals),
        record_counts=tuple(
            RecordCount(kind=kind, count=len(refs), sources=tuple(refs))
            for kind, refs in sorted(counts.items())
        ),
        retrieval_complete=retrieval_complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )
