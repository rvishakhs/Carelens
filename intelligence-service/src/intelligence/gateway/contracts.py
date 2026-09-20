from typing import Literal, Protocol

from pydantic import Field

from intelligence.core.contracts import Contract

HandoverSection = Literal[
    "care_delivered",
    "nutrition_hydration",
    "mobility",
    "continence",
    "mood_behaviour",
    "communication",
    "sleep",
    "pain",
    "falls_incidents",
    "wounds",
    "documented_follow_up",
]


class PseudonymisedEvidence(Contract):
    source_alias: str

    category: HandoverSection

    # Prepared by the gateway; preserves relevant time meaning.
    time_label: str
    time_precision: Literal["timestamp", "date", "unknown"]

    # Minimised and pseudonymised clinical content.
    content: str = Field(min_length=1)


class CalculatedMetric(Contract):
    metric_alias: str
    name: str

    # Calculated in trusted code, not by the model.
    value: float | None
    unit: str

    source_aliases: tuple[str, ...]
    coverage: Literal["complete", "partial", "unavailable"]


class HandoverPayload(Contract):
    resident_alias: str
    intent: Literal["handover"] = "handover"

    period_label: str
    evidence: tuple[PseudonymisedEvidence, ...]
    metrics: tuple[CalculatedMetric, ...]

    coverage_warnings: tuple[str, ...] = ()


class HandoverClaim(Contract):
    section: HandoverSection
    text: str = Field(min_length=1)

    source_aliases: tuple[str, ...] = Field(min_length=1)
    metric_aliases: tuple[str, ...] = ()


class HandoverOutput(Contract):
    resident_alias: str
    claims: tuple[HandoverClaim, ...]


class HandoverProvider(Protocol):
    async def generate(
        self,
        payload: HandoverPayload,
    ) -> HandoverOutput: ...


# Existing structured demo contracts remain separate from free-text handover contracts.
class SafePayload(Contract):
    resident_alias: str = "RESIDENT_A"
    intent: Literal["history", "handover"]
    source_aliases: tuple[str, ...]
    consumed_ml: int | None = Field(ge=0)
    offered_ml: int | None = Field(ge=0)


class ProviderClaim(Contract):
    resident_alias: str
    source_aliases: tuple[str, ...]
    metric: Literal["consumed_ml", "offered_ml", "no_records"]
    value: int | None


class ProviderOutput(Contract):
    claims: tuple[ProviderClaim, ...]


class Provider(Protocol):
    async def generate(self, payload: SafePayload) -> ProviderOutput: ...
