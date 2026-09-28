"""Internal clinical rendering. Output is NOT provider-safe."""

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from intelligence.core.contracts import Contract, Evidence, SourceRef
from intelligence.gateway.contracts import HandoverSection


class EvidenceRenderingError(ValueError):
    """Evidence could not be rendered using the approved field policy."""


class RenderedField(Contract):
    name: str
    value: str | int | float | bool


class RenderedEvidence(Contract):
    # Internal reference: the gateway must replace this with an alias.
    reference: SourceRef

    category: HandoverSection
    context: Literal["shift", "date_context", "unknown_time"]

    time_label: str
    time_precision: Literal["timestamp", "date", "unknown"]

    fields: tuple[RenderedField, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderRule:
    kind: str
    category: HandoverSection
    fields: tuple[str, ...]


# Source-specific allowlists. Do not replace these with clinical_data.items().
RULES: dict[str, RenderRule] = {
    "fluid_intake_records": RenderRule(
        "fluid_intake",
        "nutrition_hydration",
        (
            "volume_ml",
            "fluid_type",
            "thickener_level",
            "method",
            "notes",
        ),
    ),
    "food_intake_records": RenderRule(
        "meal",
        "nutrition_hydration",
        (
            "meal_type",
            "percentage_eaten",
            "method",
            "texture_modified",
            "notes",
        ),
    ),
    "weight_records": RenderRule(
        "weight",
        "clinical_observations",
        ("weight_kg", "height_cm", "bmi", "notes"),
    ),
    "vital_signs_records": RenderRule(
        "vitals",
        "clinical_observations",
        (
            "blood_pressure_systolic",
            "blood_pressure_diastolic",
            "heart_rate_bpm",
            "respiratory_rate",
            "oxygen_saturation_pct",
            "temperature_celsius",
            "blood_glucose_mmol",
            "news2_score",
            "notes",
        ),
    ),
    "mobility_observations": RenderRule(
        "mobility",
        "mobility",
        (
            "activity",
            "distance_or_duration",
            "assistance_given",
            "notes",
        ),
    ),
    "continence_records": RenderRule(
        "continence",
        "continence",
        (
            "event_type",
            "product_used",
            "bowel_movement",
            "bristol_type",
            "urine_output_ml",
            "skin_condition",
            "notes",
        ),
    ),
    "wellbeing_records": RenderRule(
        "wellbeing",
        "mood_behaviour",
        ("mood", "engagement_level", "notes"),
    ),
    "behaviour_records": RenderRule(
        "behaviour",
        "mood_behaviour",
        (
            "behaviour_type",
            "antecedent",
            "behaviour_description",
            "consequence",
            "duration_minutes",
            "triggers_suspected",
            "de_escalation_used",
            "harm_to_self_or_others",
        ),
    ),
    "communication_logs": RenderRule(
        "communication",
        "communication",
        (
            "interaction_summary",
            "mood_during_interaction",
            "notes",
        ),
    ),
    "sleep_records": RenderRule(
        "sleep",
        "sleep",
        (
            "settled_time",
            "woke_time",
            "night_wakings",
            "quality",
            "notes",
        ),
    ),
    "pain_assessments": RenderRule(
        "pain",
        "pain",
        (
            "scale_type",
            "score",
            "location",
            "pain_behaviours",
            "intervention",
            "effective",
            "notes",
        ),
    ),
    "falls_incidents": RenderRule(
        "fall",
        "falls_incidents",
        (
            "location",
            "witnessed",
            "severity",
            "injuries",
            "likely_cause",
            "action_taken",
            "post_fall_observations_required",
            "family_informed",
        ),
    ),
    "incidents": RenderRule(
        "incident",
        "falls_incidents",
        (
            "incident_type",
            "location",
            "description",
            "immediate_action",
            "family_informed",
            "investigation_status",
            "investigation_outcome",
        ),
    ),
    "wound_records": RenderRule(
        "wound",
        "wounds",
        (
            "body_location",
            "wound_type",
            "grade_or_category",
            "length_cm",
            "width_cm",
            "depth_cm",
            "status",
            "treatment_plan",
            "healed_date",
        ),
    ),
}


def _render_time(
    evidence: Evidence,
    zone: ZoneInfo,
) -> tuple[
    Literal["shift", "date_context", "unknown_time"],
    str,
]:
    if evidence.time_precision == "date":
        if evidence.source_date is None:
            raise EvidenceRenderingError("Missing source date")

        return (
            "date_context",
            (
                f"Source date: {evidence.source_date.isoformat()}; "
                "exact event time unavailable; date context only"
            ),
        )

    if evidence.time_precision == "unknown":
        return (
            "unknown_time",
            "Event time unknown; cannot assign to this shift",
        )

    instant: datetime | None
    if evidence.time_basis == "effective":
        instant = evidence.effective_at
        label = "Clinical event time"
    elif evidence.time_basis == "recorded":
        instant = evidence.recorded_at
        label = "Recording time; event time unavailable"
    else:
        raise EvidenceRenderingError("Invalid timestamp basis")

    if instant is None or instant.utcoffset() is None:
        raise EvidenceRenderingError("Missing timezone-aware timestamp")

    return (
        "shift",
        f"{label}: {instant.astimezone(zone).isoformat()}",
    )


def render_evidence(
    evidence: Evidence,
    *,
    care_home_timezone: str,
    max_field_characters: int = 8_000,
) -> RenderedEvidence:
    """Render evidence already authorised and assembled for a shift.

    Does not perform authorisation, shift filtering or pseudonymisation.
    """
    if max_field_characters <= 0:
        raise ValueError("max_field_characters must be positive")

    rule = RULES.get(evidence.reference.source_type)

    if rule is None:
        raise EvidenceRenderingError("Unsupported source type")

    if evidence.kind != rule.kind:
        raise EvidenceRenderingError("Source type and kind do not match")

    context, time_label = _render_time(
        evidence,
        ZoneInfo(care_home_timezone),
    )

    fields: list[RenderedField] = []

    for name in rule.fields:
        value = evidence.clinical_data.get(name)

        # Missing values must not become negative clinical findings.
        if value is None:
            continue

        if isinstance(value, str):
            value = value.strip()

            if not value:
                continue

            if len(value) > max_field_characters:
                # Do not truncate: the omitted part could change meaning.
                raise EvidenceRenderingError(
                    "Clinical field exceeds rendering limit"
                )

        elif isinstance(value, bool):
            # Preserve False, rather than treating it as absent.
            pass

        elif isinstance(value, int):
            pass

        elif isinstance(value, float):
            if not math.isfinite(value):
                raise EvidenceRenderingError(
                    "Clinical field contains a non-finite number"
                )

        else:
            # No arbitrary dictionary/list serialization.
            raise EvidenceRenderingError(
                "Clinical field has an unsupported value type"
            )

        fields.append(RenderedField(name=name, value=value))

    warnings: list[str] = []

    if not fields:
        warnings.append("no_allowlisted_clinical_fields")

    if evidence.is_implausible:
        warnings.append("source_marked_implausible")

    if context == "date_context":
        warnings.append("date_only_context_not_confirmed_shift_event")
    elif context == "unknown_time":
        warnings.append("event_time_unknown")

    return RenderedEvidence(
        reference=evidence.reference,
        category=rule.category,
        context=context,
        time_label=time_label,
        time_precision=evidence.time_precision,
        fields=tuple(fields),
        warnings=tuple(warnings),
    )


def internal_content_json(rendered: RenderedEvidence) -> str:
    """Stable internal representation; still requires gateway processing."""
    return json.dumps(
        {
            "fields": {
                field.name: field.value
                for field in rendered.fields
            },
            "quality_warnings": list(rendered.warnings),
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )