from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from intelligence.core.contracts import Evidence, SourceRef
from intelligence.handover.rendering import (
    EvidenceRenderingError,
    internal_content_json,
    render_evidence,
)


def make_evidence(
    *,
    source_type="mobility_observations",
    kind="mobility",
    clinical_data=None,
    date_only=False,
    is_implausible=False,
):
    return Evidence(
        tenant_id=uuid4(),
        resident_id=uuid4(),
        reference=SourceRef(
            source_system="Carelens_connector",
            source_type=source_type,
            source_id=uuid4(),
            version="unversioned",
        ),
        clinical_data=clinical_data or {},
        effective_at=(
            None
            if date_only
            else datetime(2026, 9, 28, 10, tzinfo=UTC)
        ),
        source_date=date(2026, 9, 28) if date_only else None,
        time_basis="effective",
        time_precision="date" if date_only else "timestamp",
        kind=kind,
        is_implausible=is_implausible,
    )


def test_mobility_preserves_assistance_and_unsteadiness():
    evidence = make_evidence(
        clinical_data={
            "activity": "Walked to dining room",
            "assistance_given": "One member of staff",
            "notes": "Unsteady when turning",
            "recorded_by": "PRIVATE_STAFF_ID",
            "photo_url": "PRIVATE_PHOTO_URL",
        }
    )

    rendered = render_evidence(
        evidence,
        care_home_timezone="Europe/London",
    )

    content = internal_content_json(rendered)

    assert rendered.category == "mobility"
    assert "One member of staff" in content
    assert "Unsteady when turning" in content
    assert "PRIVATE_STAFF_ID" not in content
    assert "PRIVATE_PHOTO_URL" not in content
    assert rendered.reference == evidence.reference


def test_false_and_zero_are_preserved():
    evidence = make_evidence(
        source_type="continence_records",
        kind="continence",
        clinical_data={
            "bowel_movement": False,
            "urine_output_ml": 0,
        },
    )

    rendered = render_evidence(
        evidence,
        care_home_timezone="Europe/London",
    )

    values = {field.name: field.value for field in rendered.fields}

    assert values["bowel_movement"] is False
    assert values["urine_output_ml"] == 0


def test_date_only_wound_is_context():
    evidence = make_evidence(
        source_type="wound_records",
        kind="wound",
        clinical_data={"body_location": "Left shin"},
        date_only=True,
    )

    rendered = render_evidence(
        evidence,
        care_home_timezone="Europe/London",
    )

    assert rendered.context == "date_context"
    assert rendered.time_precision == "date"
    assert "exact event time unavailable" in rendered.time_label
    assert (
        "date_only_context_not_confirmed_shift_event"
        in rendered.warnings
    )


def test_source_quality_flag_is_preserved():
    rendered = render_evidence(
        make_evidence(
            clinical_data={"activity": "Walking"},
            is_implausible=True,
        ),
        care_home_timezone="Europe/London",
    )

    assert "source_marked_implausible" in rendered.warnings


def test_source_kind_mismatch_fails():
    with pytest.raises(EvidenceRenderingError):
        render_evidence(
            make_evidence(kind="pain"),
            care_home_timezone="Europe/London",
        )


@pytest.mark.parametrize(
    "notes",
    [{"unexpected": "nested object"}, ["unexpected list"], float("inf")],
)
def test_unexpected_field_values_fail(notes):
    with pytest.raises(EvidenceRenderingError):
        render_evidence(
            make_evidence(clinical_data={"notes": notes}),
            care_home_timezone="Europe/London",
        )


def test_long_text_fails_instead_of_being_truncated():
    with pytest.raises(EvidenceRenderingError):
        render_evidence(
            make_evidence(clinical_data={"notes": "x" * 101}),
            care_home_timezone="Europe/London",
            max_field_characters=100,
        )


def test_empty_content_has_a_warning_not_a_normal_finding():
    rendered = render_evidence(
        make_evidence(clinical_data={"recorded_by": "PRIVATE"}),
        care_home_timezone="Europe/London",
    )

    assert rendered.fields == ()
    assert "no_allowlisted_clinical_fields" in rendered.warnings