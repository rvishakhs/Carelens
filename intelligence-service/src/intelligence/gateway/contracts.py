from pydantic import Field, model_validator
from decimal import Decimal
from typing import Annotated, Literal, Protocol

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
    "clinical_observations"
]

# Initial operational limits. Tune using representative pilot records.
MAX_EVIDENCE = 500
MAX_METRICS = 100
MAX_CLAIMS = 80
MAX_CONTENT_CHARACTERS = 8_000
MAX_CLAIM_CHARACTERS = 2_000
MAX_WARNINGS = 100

ResidentAlias = Annotated[
    str,
    Field(pattern=r"^RESIDENT_[0-9]{3,6}$"),
]

SourceAlias = Annotated[
    str,
    Field(pattern=r"^SRC_[0-9]{3,6}$"),
]

MetricAlias = Annotated[
    str,
    Field(pattern=r"^METRIC_[0-9]{3,6}$"),
]

WarningText = Annotated[
    str,
    Field(min_length=1, max_length=500),
]

EvidenceContext = Literal[
    "shift",
    "date_context",
    "unknown_time",
]

ClaimContext = Literal[
    "shift",
    "date_context",
    "unknown_time",
    "mixed",
]

MetricStatus = Literal[
    "complete",
    "partial",
    "no_records",
    "ambiguous",
]

NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=0, allow_inf_nan=False),
]

class PseudonymisedEvidence(Contract):
    source_alias: SourceAlias
    category: HandoverSection

    context: EvidenceContext
    time_precision: Literal["timestamp", "date", "unknown"]

    # Gateway-prepared, minimised time description.
    time_label: str = Field(min_length=1, max_length=200)

    # Only content that has passed the text privacy stage.
    content: str = Field(
        min_length=1,
        max_length=MAX_CONTENT_CHARACTERS,
    )

    quality_warnings: tuple[WarningText, ...] = Field(
        default=(),
        max_length=MAX_WARNINGS,
    )

    @model_validator(mode="after")
    def validate_temporal_context(self) -> "PseudonymisedEvidence":
        expected_precision = {
            "shift": "timestamp",
            "date_context": "date",
            "unknown_time": "unknown",
        }

        if self.time_precision != expected_precision[self.context]:
            raise ValueError(
                "Evidence context and time precision disagree"
            )

        return self




class CalculatedMetric(Contract):
    metric_alias: MetricAlias

    metric: Literal["consumed_ml", "offered_ml"]
    category: Literal["nutrition_hydration"] = "nutrition_hydration"

    status: MetricStatus

    # A usable complete total. Otherwise None.
    value: NonNegativeDecimal | None = None

    # Recorded subtotal; not necessarily a complete period total.
    known_subtotal: NonNegativeDecimal

    unit: Literal["ml"] = "ml"
    context: Literal["shift"] = "shift"

    source_aliases: tuple[SourceAlias, ...] = Field(
        default=(),
        max_length=MAX_EVIDENCE,
    )

    @model_validator(mode="after")
    def validate_metric(self) -> "CalculatedMetric":
        if len(set(self.source_aliases)) != len(self.source_aliases):
            raise ValueError("Duplicate metric source aliases")

        if self.status == "complete":
            if self.value is None:
                raise ValueError("Complete metric requires a value")

            if self.value != self.known_subtotal:
                raise ValueError(
                    "Complete metric value must equal its subtotal"
                )

            if not self.source_aliases:
                raise ValueError(
                    "Complete metric requires supporting sources"
                )

        elif self.value is not None:
            raise ValueError(
                "Incomplete metric must not expose a complete total"
            )

        if self.status == "no_records":
            if self.known_subtotal != Decimal("0"):
                raise ValueError(
                    "No-records metric must have a zero subtotal"
                )

            if self.source_aliases:
                raise ValueError(
                    "No-records metric cannot cite measurement sources"
                )

        return self



class HandoverPayload(Contract):
    resident_alias: ResidentAlias
    intent: Literal["handover"] = "handover"

    period_label: str = Field(min_length=1, max_length=200)

    evidence: tuple[PseudonymisedEvidence, ...] = Field(
        max_length=MAX_EVIDENCE,
    )

    metrics: tuple[CalculatedMetric, ...] = Field(
        max_length=MAX_METRICS,
    )

    coverage_complete: bool

    # Only gateway-approved warning text or controlled messages.
    coverage_warnings: tuple[WarningText, ...] = Field(
        default=(),
        max_length=MAX_WARNINGS,
    )


class HandoverClaim(Contract):
    section: HandoverSection
    context: ClaimContext

    text: str = Field(
        min_length=1,
        max_length=MAX_CLAIM_CHARACTERS,
    )

    source_aliases: tuple[SourceAlias, ...] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE,
    )

    metric_aliases: tuple[MetricAlias, ...] = Field(
        default=(),
        max_length=MAX_METRICS,
    )


class HandoverOutput(Contract):
    resident_alias: ResidentAlias

    claims: tuple[HandoverClaim, ...] = Field(
        max_length=MAX_CLAIMS,
    )


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
