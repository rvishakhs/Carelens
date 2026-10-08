"""Evidence-backed prose, shared by provider validation and legacy presentation.

No clinical inference, new calculations or access to unminimised source text.
"""

import json
import re
from datetime import datetime
from decimal import Decimal


def number(value):
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        text = format(Decimal(str(value)), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    return str(value)


def readable_time(label: str) -> str:
    for prefix, wording in (
        ("Clinical event time: ", "At"),
        ("Recording time; event time unavailable: ", "Recorded at"),
    ):
        if label.startswith(prefix):
            try:
                instant = datetime.fromisoformat(label[len(prefix) :])
                result = f"{wording} {instant:%H:%M} on {instant:%d %b}"
                if wording == "Recorded at":
                    result += " (event time unavailable)"
                return result
            except ValueError:
                pass
    # Retain date-only / unknown-time qualifiers verbatim.
    return label


def evidence_prose(time_label: str, content: str) -> str:
    try:
        fields = json.loads(content)
    except (ValueError, TypeError):
        return f"{readable_time(time_label)}: {content}"
    if not isinstance(fields, dict):
        return f"{readable_time(time_label)}: recorded details could not be summarised."
    remaining = dict(fields)
    parts = []
    is_care = any(k.startswith("status_") for k in fields)
    stopped = next(
        (
            word
            for key, word in (
                ("status_declined", "Care was declined"),
                ("status_refused", "Care was refused"),
                ("status_not_applicable", "Care was recorded as not applicable"),
            )
            if fields.get(key) is True
        ),
        None,
    )
    if stopped:
        # Options on a non-completed care event do not prove care was delivered.
        return f"{readable_time(time_label)}: {stopped.lower()}."
    for key in ("status_completed", "status_declined", "status_refused", "status_not_applicable"):
        remaining.pop(key, None)
    if fields.get("offered_ml") is not None:
        parts.append(f"{number(fields['offered_ml'])} ml of fluid was offered")
        remaining.pop("offered_ml", None)
    if fields.get("estimated_consumed_ml") is not None:
        amount = (
            "half taken"
            if fields.get("amount_half") is True
            else "all taken"
            if fields.get("amount_all") is True
            else "recorded choices"
        )
        parts.append(
            f"intake was estimated at {number(fields['estimated_consumed_ml'])} ml "
            f"from {amount}, not measured"
        )
        remaining.pop("estimated_consumed_ml", None)
        remaining.pop("amount_half", None)
        remaining.pop("amount_all", None)
    if fields.get("is_walk") is True:
        parts.append("a walk was recorded")
    if fields.get("is_wandering") is True:
        parts.append("wandering was recorded")
    # These false values classify templates; they are NOT negative clinical findings.
    remaining.pop("is_walk", None)
    remaining.pop("is_wandering", None)
    phrases = {
        "food_sandwich": "the meal included a sandwich",
        "meal_size_medium": "a medium meal portion was offered",
        "distance_medium": "the walking distance was recorded as medium",
        "trigger_unknown": "the trigger was recorded as unknown",
        "drink_tea": "the drink was tea",
        "wandering_in_garden": "wandering was recorded in the garden",
        "meal_most_eaten": "most of the meal was eaten",
        "meal_about_half_eaten": "about half of the meal was eaten",
        "amount_half": "half of the drink was recorded as taken",
        "amount_all": "all of the drink was recorded as taken",
        "walking_frame_used": "a walking frame was used",
        "supervision_only": "assistance was recorded as supervision only",
        "settled": "the recorded response was settled",
        "remained_on_premises": "the resident remained on the premises",
        "reassurance_or_distraction": "reassurance or distraction was recorded",
    }
    for key, phrase in phrases.items():
        if remaining.get(key) is True:
            parts.append(phrase)
            remaining.pop(key)
    if is_care and remaining.get("duration_minutes") is not None:
        parts.append(
            f"the care event duration was recorded as {number(remaining.pop('duration_minutes'))} minutes"
        )
    labels = {
        "volume_ml": "Recorded fluid intake (ml)",
        "percentage_eaten": "Meal eaten (%)",
        "weight_kg": "Weight (kg)",
        "height_cm": "Height (cm)",
        "bmi": "BMI",
        "heart_rate_bpm": "Heart rate (bpm)",
        "oxygen_saturation_pct": "Oxygen saturation (%)",
        "temperature_celsius": "Temperature (°C)",
        "blood_glucose_mmol": "Blood glucose (mmol/L)",
        "blood_pressure_systolic": "Systolic blood pressure (mmHg)",
        "blood_pressure_diastolic": "Diastolic blood pressure (mmHg)",
        "respiratory_rate": "Respiratory rate",
        "news2_score": "Recorded NEWS2 score",
    }
    for key, value in remaining.items():
        if value is None:
            continue
        label = labels.get(key, key.replace("_", " ").capitalize())
        rendered = ("yes" if value else "no") if isinstance(value, bool) else number(value)
        parts.append(f"{label}: {rendered}")
    if not parts:
        parts.append(
            "care was recorded as completed; further details are unavailable in this summary"
            if fields.get("status_completed")
            else "no approved clinical details are available for this record"
        )
    return f"{readable_time(time_label)}: " + "; ".join(parts) + "."


def metric_prose(metric, value, subtotal, status, unit="ml") -> str:
    label = {"offered_ml": "fluid offered", "consumed_ml": "fluid intake (excluding estimates)"}.get(
        metric, metric.replace("_", " ")
    )
    if status == "complete":
        return f"Recorded {label} total: {number(value)} {unit}."
    qualifier = " Records are ambiguous and need reconciliation." if status == "ambiguous" else ""
    return (
        f"Recorded {label}: {number(subtotal)} {unit} across available records; "
        f"the full-shift total is unavailable.{qualifier}"
    )


def legacy_claim(text: str) -> str:
    """Display-only compatibility; persisted originals and staff revisions stay unchanged."""
    time_label, separator, content = text.partition(". Recorded content: ")
    if separator and time_label.startswith(
        ("Clinical event time:", "Recording time;", "Source date:", "Event time unknown;")
    ):
        try:
            fields = json.loads(content)
        except ValueError:
            return text
        if isinstance(fields, dict):
            return evidence_prose(time_label, content)
    match = re.fullmatch(
        r"Recorded (consumed_ml|offered_ml): known subtotal ([0-9.]+) ml; "
        r"status (partial|ambiguous|no_records); complete total unavailable\.",
        text,
    )
    if match:
        return metric_prose(match[1], None, match[2], match[3])
    match = re.fullmatch(r"Recorded (consumed_ml|offered_ml): ([0-9.]+) ml \(complete\)\.", text)
    if match:
        return metric_prose(match[1], match[2], match[2], "complete")
    return text


WARNING_LABELS = {
    "care_event_free_text_and_unmapped_fields_withheld": (
        "Free-text care notes are not reproduced; only approved mapped details are included. "
        "Review original care records for additional context and unrecognised fields."
    ),
    "consumed_volume_estimated_from_options_not_measured": (
        "Some fluid intake amounts are estimates from recorded choices, not measured intake."
    ),
    "unmapped_care_event_category": ("Some care categories could not be summarised."),
    "no_allowlisted_clinical_fields": (
        "A record has no approved clinical details available for this summary."
    ),
    "source_marked_implausible": ("A source record was flagged as implausible and requires review."),
    "date_only_context_not_confirmed_shift_event": (
        "Some records have a date only and cannot be assigned confidently to this shift."
    ),
    "event_time_unknown": ("Some records have no known event time."),
    "A meal record has no consumed percentage.": (
        "An exact meal percentage is unavailable; qualitative amounts such as ‘most’ are "
        "preserved where recorded."
    ),
    "A fluid amount is missing; complete consumed total is unavailable.": (
        "Measured fluid intake is missing for some records; estimates do not count as measured intake."
    ),
    (
        "Clinical observations and care events retrieved; complete handover coverage and source "
        "snapshot consistency have not been established."
    ): (
        "This draft uses the retrieved observations and care events. Complete shift coverage and "
        "a consistent source snapshot have not been verified."
    ),
}
