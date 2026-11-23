from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from app.modules.resident_search.evidence.topics import ResidentTopic

TEMPLATE_CODE_TOPICS = MappingProxyType({
    "standing_hoist_transfer": frozenset({
        ResidentTopic.MOBILITY,
        ResidentTopic.TRANSFER,
    }),
    "meal_support": frozenset({
        ResidentTopic.NUTRITION,
    }),
    "fluid_intake": frozenset({
        ResidentTopic.HYDRATION,
    }),
    "sleep_check": frozenset({
        ResidentTopic.SLEEP,
    }),
    "fall incident": frozenset({
        ResidentTopic.FALL,
        ResidentTopic.MOBILITY,
    }),

    "repositioning": frozenset({
        ResidentTopic.SKIN,
        ResidentTopic.WOUND,
    }),

    "communication support": frozenset({
        ResidentTopic.COMMUNICATION,
    }),

    "toileting support": frozenset({
        ResidentTopic.CONTINENCE,
        ResidentTopic.PERSONAL_CARE,
    }),
})




TEMPLATE_NAME_TOPICS = MappingProxyType({
    "standing hoist transfer": frozenset({
        ResidentTopic.MOBILITY,
        ResidentTopic.TRANSFER,
    }),
    "meal support": frozenset({
        ResidentTopic.NUTRITION,
    }),
    "fluid intake": frozenset({
        ResidentTopic.HYDRATION,
    }),
    "sleep check": frozenset({
        ResidentTopic.SLEEP,
    }),
})

CATEGORY_NAME_TOPICS = MappingProxyType({
    "mobility": frozenset({
        ResidentTopic.MOBILITY,
    }),
    "nutrition & hydration": frozenset({
        ResidentTopic.NUTRITION,
        ResidentTopic.HYDRATION,
    }),
    "communication": frozenset({
        ResidentTopic.COMMUNICATION,
    }),
    "sleeping": frozenset({
        ResidentTopic.SLEEP,
    }),
})

def normalise_label(value: str | None) -> str:
    return " ".join((value or "").casefold().split())

@dataclass(frozen=True)
class TopicAssignment:
    topics: frozenset[ResidentTopic]
    basis: Literal[
        "template_code",
        "template_name",
        "category",
        "unmapped",
    ]

def assign_care_event_topics(
    *,
    template_code: str | None,
    template_name: str | None,
    category_name: str | None,
) -> TopicAssignment:
    code = normalise_label(template_code)
    if code and code in TEMPLATE_CODE_TOPICS:
        return TopicAssignment(
            topics=TEMPLATE_CODE_TOPICS[code],
            basis="template_code",
        )

    name = normalise_label(template_name)
    if name and name in TEMPLATE_NAME_TOPICS:
        return TopicAssignment(
            topics=TEMPLATE_NAME_TOPICS[name],
            basis="template_name",
        )

    category = normalise_label(category_name)
    if category and category in CATEGORY_NAME_TOPICS:
        return TopicAssignment(
            topics=CATEGORY_NAME_TOPICS[category],
            basis="category",
        )

    return TopicAssignment(
        topics=frozenset({ResidentTopic.CARE_RECORD}),
        basis="unmapped",
    )
