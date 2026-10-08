import json
from types import SimpleNamespace

from intelligence.gateway.validation import evidence_claim_text, metric_claim_text
from intelligence.handover.prose import legacy_claim


def test_numeric_precision_is_not_silently_rounded():
    assert "123.456789" in render(volume_ml=123.456789)


def render(**fields):
    return evidence_claim_text(
        SimpleNamespace(
            time_label="Clinical event time: 2026-10-07T19:14:12.706721+01:00",
            content=json.dumps(fields),
        )
    )


def test_estimated_drink_reads_as_handover_without_implying_measurement():
    text = render(
        status_completed=True,
        offered_ml=150,
        estimated_consumed_ml=75.0,
        amount_half=True,
        is_walk=False,
        is_wandering=False,
    )
    assert text == (
        "At 19:14 on 07 Oct: 150 ml of fluid was offered; intake was estimated at 75 ml "
        "from half taken, not measured."
    )
    assert "{" not in text and "is_walk" not in text and "no wandering" not in text


def test_meal_preserves_most_without_fabricating_percentage():
    text = render(status_completed=True, meal_most_eaten=True, duration_minutes=10)
    assert "most of the meal was eaten" in text
    assert "%" not in text and "75" not in text


def test_mobility_does_not_turn_care_duration_into_walk_duration():
    text = render(
        status_completed=True,
        is_walk=True,
        walking_frame_used=True,
        supervision_only=True,
        duration_minutes=15,
    )
    assert "a walk was recorded" in text and "walking frame was used" in text
    assert "supervision only" in text
    assert "care event duration was recorded as 15 minutes" in text
    assert "walked for 15" not in text


def test_behaviour_does_not_invent_causality_or_clinical_stability():
    text = render(
        status_completed=True,
        is_wandering=True,
        reassurance_or_distraction=True,
        settled=True,
        remained_on_premises=True,
    )
    assert "wandering was recorded" in text
    assert "recorded response was settled" in text
    assert "reassurance or distraction" in text
    assert "because" not in text and "stable" not in text


def test_refused_care_does_not_claim_selected_options_were_delivered():
    text = render(status_refused=True, meal_most_eaten=True, walking_frame_used=True)
    assert "care was refused" in text
    assert "meal was eaten" not in text and "frame was used" not in text


def test_incomplete_total_stays_incomplete():
    text = metric_claim_text(
        SimpleNamespace(metric="offered_ml", value=None, known_subtotal=430, status="partial", unit="ml")
    )
    assert "fluid offered: 430 ml across available records" in text
    assert "full-shift total is unavailable" in text


def test_unknown_time_retains_qualifier_and_false_clinical_fields():
    text = evidence_claim_text(
        SimpleNamespace(
            time_label="Event time unknown; cannot assign to this shift",
            content='{"witnessed":false,"notes":"Reviewed text"}',
        )
    )
    assert "cannot assign to this shift" in text and "Witnessed: no" in text
    assert "Reviewed text" in text


def test_legacy_display_conversion_leaves_unrecognised_text_unchanged():
    raw = 'Clinical event time: 2026-10-07T19:14:12+01:00. Recorded content: {"offered_ml":150}'
    assert legacy_claim(raw) == "At 19:14 on 07 Oct: 150 ml of fluid was offered."
    assert legacy_claim("Staff recorded that care was refused.") == "Staff recorded that care was refused."
    assert (
        legacy_claim("Clinical event time: unknown. Recorded content: broken")
        == "Clinical event time: unknown. Recorded content: broken"
    )
