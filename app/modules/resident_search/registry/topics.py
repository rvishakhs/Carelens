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

