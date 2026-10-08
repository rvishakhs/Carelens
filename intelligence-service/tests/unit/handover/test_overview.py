import json
from uuid import uuid4

from intelligence.core.contracts import Claim, SourceRef
from intelligence.handover.contracts import HandoverSection
from intelligence.handover.overview import overview_text
from intelligence.handover.prose import evidence_prose


def claim(**fields):
    return Claim(
        text=evidence_prose("Clinical event time: 2026-10-07T19:14:12+01:00", json.dumps(fields)),
        sources=(SourceRef(source_type="care_events", source_id=uuid4(), version="1"),),
    )


def test_flowing_narrative_preserves_specifics_without_inventing_causality():
    result = overview_text(
        (
            HandoverSection(
                category="nutrition_hydration",
                claims=(
                    claim(status_completed=True, meal_most_eaten=True, food_sandwich=True),
                    claim(status_completed=True, offered_ml=150, estimated_consumed_ml=75, amount_half=True),
                    claim(
                        status_completed=True,
                        offered_ml=280,
                        estimated_consumed_ml=280,
                        amount_all=True,
                        drink_tea=True,
                    ),
                ),
            ),
            HandoverSection(
                category="mobility",
                claims=(
                    claim(
                        status_completed=True,
                        is_walk=True,
                        distance_medium=True,
                        walking_frame_used=True,
                        supervision_only=True,
                    ),
                ),
            ),
            HandoverSection(
                category="mood_behaviour",
                claims=(
                    claim(
                        status_completed=True,
                        is_wandering=True,
                        wandering_in_garden=True,
                        trigger_unknown=True,
                        reassurance_or_distraction=True,
                        settled=True,
                        remained_on_premises=True,
                    ),
                ),
            ),
        )
    )
    for phrase in (
        "sandwich",
        "approximately 355 ml",
        "tea taken in full",
        "medium-distance walk",
        "walking frame and supervision",
        "in the garden",
        "trigger recorded as unknown",
        "reassurance or distraction",
        "settled response",
        "remaining on the premises",
    ):
        assert phrase in result
    for invented in ("due to", "safely", "throughout", "reassurance and distraction", "normal"):
        assert invented not in result
    assert "\n" not in result


def test_missing_estimate_or_duplicate_source_never_creates_consumed_total():
    drink = claim(status_completed=True, offered_ml=150, estimated_consumed_ml=75, amount_half=True)
    missing = claim(status_completed=True, offered_ml=280)
    for records in ((drink, missing), (drink, drink)):
        result = overview_text((HandoverSection(category="nutrition_hydration", claims=records),))
        assert "Estimated fluid intake" not in result


def test_sample_becomes_short_shift_overview_not_record_replay():
    sections = (
        HandoverSection(
            category="nutrition_hydration",
            claims=(
                claim(status_completed=True, offered_ml=150, estimated_consumed_ml=75, amount_half=True),
                claim(status_completed=True, offered_ml=280, estimated_consumed_ml=280, amount_all=True),
                claim(status_completed=True, meal_most_eaten=True, duration_minutes=10),
            ),
        ),
        HandoverSection(
            category="mobility",
            claims=(
                claim(
                    status_completed=True,
                    is_walk=True,
                    walking_frame_used=True,
                    supervision_only=True,
                    duration_minutes=15,
                ),
            ),
        ),
        HandoverSection(
            category="mood_behaviour",
            claims=(
                claim(
                    status_completed=True,
                    is_wandering=True,
                    settled=True,
                    reassurance_or_distraction=True,
                    remained_on_premises=True,
                ),
            ),
        ),
    )
    result = overview_text(sections)
    assert result.startswith("The resident ate most")
    assert "a settled response" in result
    assert "recorded meal portions" in result
    assert "approximately 355 ml across 2 recorded drinks" in result
    assert "walking frame and supervision" in result
    assert len(result.split()) < 100
    for forbidden in ("19:14", "150", "280", "minutes", "normal", "no concerns", "stable", "adequate"):
        assert forbidden not in result
    assert "\n" not in result


def test_refusal_and_unrecognised_clinical_detail_are_not_hidden():
    refusal = claim(status_refused=True)
    fall = Claim(
        text="A fall with an injury was recorded.",
        sources=(SourceRef(source_type="falls_incidents", source_id=uuid4(), version="1"),),
    )
    result = overview_text(
        (
            HandoverSection(
                category="nutrition_hydration",
                claims=(claim(status_completed=True, meal_most_eaten=True), refusal),
            ),
            HandoverSection(category="falls_incidents", claims=(fall,)),
        )
    )
    assert result.startswith(fall.text)
    assert refusal.text in result
    assert "no concerns" not in result


def test_mixed_meal_and_mobility_support_not_flattened_to_normal():
    result = overview_text(
        (
            HandoverSection(
                category="nutrition_hydration",
                claims=(
                    claim(status_completed=True, meal_most_eaten=True),
                    claim(status_completed=True, meal_about_half_eaten=True),
                ),
            ),
            HandoverSection(
                category="mobility",
                claims=(
                    claim(
                        status_completed=True, is_walk=True, walking_frame_used=True, supervision_only=True
                    ),
                    claim(status_completed=True, is_walk=True),
                ),
            ),
        )
    )
    assert "varied between about half and most" in result
    assert "Support details vary or are incomplete" in result
    assert "Mobility was supported during walking with a walking frame and supervision" not in result


def test_unknown_time_notes_cannot_be_promoted_to_shift_patterns():
    timed = claim(status_completed=True, meal_most_eaten=True)
    unknown = timed.model_copy(
        update={"text": "Event time unknown; cannot assign to this shift: most of the meal was eaten."}
    )
    assert overview_text((HandoverSection(category="nutrition_hydration", claims=(unknown,)),)) is None


def test_missing_or_unrecognised_data_does_not_create_an_all_clear():
    assert overview_text(()) is None
    assert (
        overview_text(
            (
                HandoverSection(
                    category="clinical_observations",
                    claims=(Claim(text="No approved details available", sources=()),),
                ),
            )
        )
        is None
    )


def test_declined_or_unrecognised_drink_is_retained_alongside_other_intake():
    unusual = claim(status_completed=True, offered_ml=100, notes="Swallowing concern recorded")
    result = overview_text(
        (
            HandoverSection(
                category="nutrition_hydration",
                claims=(
                    claim(status_completed=True, meal_most_eaten=True),
                    unusual,
                ),
            ),
        )
    )
    assert unusual.text in result
