from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from intelligence.core.contracts import Evidence, SourceRef
from intelligence.handover.evidence import ShiftEvidence
from intelligence.handover.metrics import MetricsInputError, calculate_handover_metrics

TENANT = UUID(int=1)
RESIDENT = UUID(int=2)


def record(number=1, *, kind="fluid_intake", hour=8, **data):
    return Evidence(
        tenant_id=TENANT,
        resident_id=RESIDENT,
        reference=SourceRef(source_type=kind, source_id=UUID(int=number), version="v1"),
        kind=kind,
        effective_at=datetime(2026, 9, 8, hour, tzinfo=UTC),
        time_basis="effective",
        time_precision="timestamp",
        clinical_data=data,
    )


def assembled(*records, date_context=(), unknown=()):
    return ShiftEvidence(
        shift_records=records,
        date_context=date_context,
        unknown_time_records=unknown,
        outside_shift_count=0,
        warnings=(),
    )


def calculate(*records, complete=True):
    return calculate_handover_metrics(assembled(*records), retrieval_complete=complete)


def test_aliases_count_once_and_decimal_arithmetic_is_exact():
    result = calculate(
        record(1, volume_ml="100.1", ml="100.1", offered_ml=200),
        record(2, hour=9, volume_ml="50.2", offered_ml=100),
    )
    assert result.consumed.value == Decimal("150.3")
    assert result.offered.value == 300
    assert len(result.consumed.sources) == 2


def test_partial_drinks_count_offer_once_and_preserve_portions():
    result = calculate(
        record(2, hour=9, consumed_ml=50, offer_id="cup-1", consumption_mode="incremental"),
        record(1, consumed_ml=100, offered_ml=200, offer_id="cup-1", consumption_mode="incremental"),
    )
    assert result.offered.value == 200
    assert result.consumed.value == 150
    assert [r.consumption_delta_ml for r in result.fluids] == [100, 50]
    assert [r.at.hour for r in result.fluids] == [8, 9]


def test_cumulative_updates_are_differences_not_additional_drinks():
    result = calculate(
        record(
            1,
            consumed_ml=100,
            offered_ml=200,
            offer_id="cup-1",
            consumption_mode="cumulative",
            opening_consumed_ml=0,
        ),
        record(2, hour=9, consumed_ml=150, offered_ml=200, offer_id="cup-1", consumption_mode="cumulative"),
    )
    assert result.consumed.value == 150
    assert result.offered.value == 200
    assert [r.consumption_delta_ml for r in result.fluids] == [100, 50]


def test_cumulative_opening_baseline_excludes_previous_shift_intake():
    result = calculate(
        record(consumed_ml=150, offer_id="cup-1", consumption_mode="cumulative", opening_consumed_ml=100)
    )
    assert result.consumed.value == 50
    assert result.offered.value is None


@pytest.mark.parametrize(
    "changes",
    [
        {"consumption_mode": "unknown"},
        {"consumption_mode": "cumulative"},
        {"consumption_mode": "cumulative", "opening_consumed_ml": 101},
        {"consumption_mode": "incremental", "opening_consumed_ml": 0},
    ],
)
def test_unknown_mode_or_invalid_baseline_withholds_consumed_total(changes):
    result = calculate(record(consumed_ml=100, offer_id="cup-1", **changes))
    assert result.consumed.status == "ambiguous"
    assert result.consumed.value is None
    assert result.fluids[0].consumption_delta_ml is None
    assert result.warnings


def test_linked_record_does_not_guess_mode_from_narrative():
    result = calculate(record(consumed_ml=100, offer_id="cup-1", notes="drank another 100"))
    assert result.consumed.status == "ambiguous"


@pytest.mark.parametrize(
    "second",
    [
        {"hour": 9, "consumed_ml": 50, "consumption_mode": "cumulative"},
        {"hour": 8, "consumed_ml": 150, "consumption_mode": "cumulative"},
        {"hour": 9, "consumed_ml": 50, "consumption_mode": "incremental"},
    ],
)
def test_decreasing_tied_or_mixed_cumulative_readings_are_ambiguous(second):
    result = calculate(
        record(1, consumed_ml=100, offer_id="cup-1", consumption_mode="cumulative", opening_consumed_ml=0),
        record(2, offer_id="cup-1", **second),
    )
    assert result.consumed.value is None
    assert result.consumed.status == "ambiguous"


def test_separate_offers_are_added_independently():
    result = calculate(
        record(1, offer_id="a", offered_ml=200, consumed_ml=100, consumption_mode="incremental"),
        record(2, offer_id="b", offered_ml=200, consumed_ml=50, consumption_mode="incremental"),
    )
    assert result.offered.value == 400
    assert result.consumed.value == 150


def test_conflicting_offer_amounts_are_not_summed():
    result = calculate(
        record(1, offer_id="a", offered_ml=200, consumed_ml=100, consumption_mode="incremental"),
        record(2, offer_id="a", offered_ml=300, consumed_ml=50, consumption_mode="incremental"),
    )
    assert result.offered.status == "ambiguous"
    assert result.offered.value is None


def test_consumption_above_linked_offer_requires_reconciliation():
    result = calculate(record(offer_id="a", offered_ml=100, consumed_ml=150, consumption_mode="incremental"))
    assert result.consumed.status == "ambiguous"


def test_missing_zero_empty_and_failed_retrieval_differ():
    missing = calculate(record())
    zero = calculate(record(volume_ml=0, offered_ml=0))
    empty = calculate()
    failed = calculate(complete=False)
    assert missing.consumed.value is None and missing.consumed.status == "partial"
    assert zero.consumed.value == 0 and zero.consumed.status == "complete"
    assert empty.consumed.value is None and empty.consumed.status == "no_records"
    assert failed.consumed.value is None and failed.consumed.status == "partial"


def test_incomplete_retrieval_returns_subtotal_not_full_total():
    result = calculate(record(volume_ml=150), complete=False)
    assert result.consumed.value is None
    assert result.consumed.known_subtotal == 150
    assert result.consumed.status == "partial"


def test_missing_group_does_not_make_other_known_portions_disappear():
    result = calculate(record(1, volume_ml=100), record(2))
    assert result.consumed.value is None
    assert result.consumed.known_subtotal == 100
    assert result.consumed.sources == (record(1).reference,)


def test_meals_are_individual_percentages_not_added_or_missing_meal_inferred():
    result = calculate(
        record(1, kind="meal", meal_type="breakfast", percentage_eaten=75, fraction_eaten=0.75),
        record(2, kind="meal", meal_type="lunch", fraction_eaten=0.5),
        record(3, kind="meal", meal_type="snack"),
    )
    assert [m.percentage_eaten for m in result.meals] == [75, 50, None]
    assert [m.meal for m in result.meals] == ["breakfast", "lunch", "snack"]
    assert result.record_counts[0].count == 3


@pytest.mark.parametrize(
    "fields",
    [
        {"volume_ml": -1},
        {"volume_ml": True},
        {"volume_ml": "NaN"},
        {"volume_ml": "Infinity"},
        {"volume_ml": "150ml"},
        {"volume_ml": 100, "ml": 200},
        {"offered_ml": []},
        {"consumption_mode": "guess"},
        {"offer_id": ""},
    ],
)
def test_invalid_fluid_values_fail_without_exposing_input(fields):
    with pytest.raises(MetricsInputError):
        calculate(record(**fields))


@pytest.mark.parametrize(
    "fields",
    [
        {"percentage_eaten": 101},
        {"fraction_eaten": 1.5},
        {"percentage_eaten": 50, "fraction_eaten": 0.75},
    ],
)
def test_invalid_meal_percentage_is_rejected(fields):
    with pytest.raises(MetricsInputError):
        calculate(record(kind="meal", **fields))


def test_scope_and_duplicate_defence():
    row = record()
    with pytest.raises(MetricsInputError, match="Duplicate"):
        calculate(row, row)
    with pytest.raises(MetricsInputError, match="Mixed"):
        calculate(row, record(2).model_copy(update={"resident_id": uuid4()}))


def test_different_sources_with_same_uuid_are_not_deduplicated():
    first = record(volume_ml=100)
    second = first.model_copy(
        update={"reference": first.reference.model_copy(update={"source_type": "other"})}
    )
    result = calculate(first, second)
    assert result.consumed.value == 200
    assert len(result.consumed.sources) == 2


def test_time_context_excluded_and_uncertain_fluid_prevents_complete_total():
    date_row = record(2).model_copy(
        update={"time_precision": "date", "effective_at": None, "source_date": date(2026, 9, 8)}
    )
    unknown = record(3, kind="sleep").model_copy(
        update={"time_precision": "unknown", "time_basis": "unknown", "effective_at": None}
    )
    result = calculate_handover_metrics(
        assembled(record(volume_ml=100), date_context=(date_row,), unknown=(unknown,)),
        retrieval_complete=True,
    )
    assert result.consumed.value is None and result.consumed.known_subtotal == 100
    assert len(result.fluids) == 1
    assert [(c.kind, c.count) for c in result.record_counts] == [("fluid_intake", 1)]


def test_record_counts_are_not_inferred_episodes_and_inputs_are_unchanged():
    rows = [
        record(1, kind="continence", notes="pad changed twice"),
        record(2, kind="fall"),
        record(3, kind="mobility"),
    ]
    before = [r.model_dump() for r in rows]
    result = calculate(*rows)
    assert {c.kind: c.count for c in result.record_counts} == {"continence": 1, "fall": 1, "mobility": 1}
    assert [r.model_dump() for r in rows] == before


def test_legacy_top_level_fields_and_recorded_time_fallback():
    row = record().model_copy(
        update={
            "consumed_ml": 100,
            "offered_ml": 200,
            "effective_at": None,
            "recorded_at": datetime(2026, 9, 8, 10, tzinfo=UTC),
            "time_basis": "recorded",
        }
    )
    result = calculate(row)
    assert result.consumed.value == 100
    assert result.fluids[0].time_basis == "recorded" and result.fluids[0].at.hour == 10


def test_real_observation_normalisation_to_shift_metrics():
    from intelligence.connectors.carelens import ObservationResponse
    from intelligence.connectors.normalise import normalise_observation
    from intelligence.core.contracts import ExecutionContext, Period
    from intelligence.handover.evidence import assemble_shift_evidence

    context = ExecutionContext(
        tenant_id=TENANT,
        service_identity="test",
        trigger="scheduled",
        authorised_resident_ids=frozenset({RESIDENT}),
        permissions=frozenset(),
    )
    transport = ObservationResponse(
        id=UUID(int=10),
        resident_id=RESIDENT,
        type="fluid_intake",
        value={"volume_ml": "150.5", "ml": "150.5"},
        recorded_at=datetime(2026, 9, 8, 9, tzinfo=UTC),
        recorded_by=None,
        is_implausible=False,
        source_type="fluid_intake_records",
        time_precision="timestamp",
    )
    row = normalise_observation(transport, context=context, expected_resident_id=RESIDENT)
    assert row is not None
    shift = assemble_shift_evidence(
        (row,),
        context=context,
        expected_resident_id=RESIDENT,
        period=Period(start=datetime(2026, 9, 8, 7, tzinfo=UTC), end=datetime(2026, 9, 8, 19, tzinfo=UTC)),
        care_home_timezone="Europe/London",
    )
    result = calculate_handover_metrics(shift, retrieval_complete=True)
    assert result.consumed.value == Decimal("150.5")
    assert result.offered.value is None
    assert result.consumed.sources[0].fingerprint == row.reference.fingerprint
