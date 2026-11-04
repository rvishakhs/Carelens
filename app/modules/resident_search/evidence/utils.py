import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

CARE_PLAN_DOMAIN_TOPICS: dict[str, set[str]] = {
    "mobility": {"mobility", "transfer", "falls"},
    "nutrition_hydration": {"nutrition", "hydration", "fluid"},
    "communication": {"communication"},
    "skin_integrity": {"skin", "pressure_area", "repositioning"},
    "continence": {"continence", "toileting"},
    "behaviour_wellbeing": {"wellbeing", "behaviour"},
    "sleep": {"sleep"},
    "medication": {"medication"},
    "pain_management": {"pain"},
    "social_activities": {"activity", "wellbeing"},
    "end_of_life": {"end_of_life"},
    "personal": {"personal_care"},
}

PLAN_TEXT_TOPICS: dict[str, set[str]] = {
    "standing aid": {"mobility", "transfer"},
    "hoist": {"mobility", "transfer"},
    "two staff": {"transfer", "staffing"},
    "wheelchair": {"mobility"},
    "walking frame": {"mobility"},
    "thickened fluids": {"nutrition", "hydration"},
    "reposition": {"skin", "repositioning"},
}


def _clean(value: object | None) -> str | None:
    """Normalise whitespace and avoid rendering empty text."""
    if value is None:
        return None

    text = " ".join(str(value).split())
    return text or None


def _topics_for_event(category_name: str, template_name: str) -> list[str]:
    text = f"{category_name} {template_name}".casefold()
    topics: set[str] = set()

    def matches(*terms: str) -> bool:
        return any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in terms)

    if matches("mobility", "transfer", "transfers", "hoist", "walking", "wheelchair"):
        topics.add("mobility")
    if matches("transfer", "transfers", "hoist"):
        topics.add("transfer")

    if matches("fall", "falls", "trip", "slip"):
        topics.update({"fall", "safety", "mobility"})

    if matches("meal", "meals", "food", "nutrition"):
        topics.add("nutrition")

    if matches("fluid", "fluids", "drink", "drinks", "hydration"):
        topics.update({"hydration", "nutrition"})

    if matches("sleep", "sleeping"):
        topics.add("sleep")

    if matches("communication", "hearing"):
        topics.add("communication")

    if matches("toilet", "toileting", "continence"):
        topics.update({"continence", "personal_care"})
    if matches("personal care", "bath", "bathing", "shower", "oral care"):
        topics.add("personal_care")

    if not topics:
        topics.add("care_record")

    return sorted(topics)


def _topics_for_care_plan(
    domain: str,
    content: str | None,
    goals: Iterable[dict[str, object]],
) -> list[str]:
    topics = set(CARE_PLAN_DOMAIN_TOPICS.get(domain, {"care_plan"}))

    goal_text = " ".join(
        str(goal.get(field) or "") for goal in goals for field in ("goal_text", "baseline", "target", "measurement")
    )

    text = f"{content or ''} {goal_text}".casefold()

    for phrase, mapped_topics in PLAN_TEXT_TOPICS.items():
        if re.search(r"\b" + re.escape(phrase) + r"\b", text):
            topics.update(mapped_topics)

    return sorted(topics)


def _measurement_value(measurement: Mapping[str, Any]) -> str | None:
    """Choose the populated measurement value without treating zero as empty."""
    if measurement["value_numeric"] is not None:
        value = str(measurement["value_numeric"])
    elif measurement["value_text"] is not None:
        value = _clean(measurement["value_text"])
    elif measurement["value_boolean"] is not None:
        value = "Yes" if measurement["value_boolean"] else "No"
    else:
        return None

    unit = _clean(measurement["unit"])
    if value is None:
        return None
    return f"{value} {unit}" if unit else value


def _care_plan_revision(
    *,
    plan: Mapping[str, Any],
    goals: list[dict[str, Any]],
) -> str:
    payload = {
        "plan": dict(plan),
        "goals": sorted(goals, key=lambda goal: str(goal["id"])),
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )

    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
