import re
from collections.abc import Mapping
from typing import Any


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
