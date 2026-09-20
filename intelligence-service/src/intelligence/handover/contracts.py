from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from intelligence.core.contracts import Claim, Contract, Period


HandoverJobState = Literal[
    "queued",
    "running",
    "draft_ready",
    "failed",
    "cancelled",
]


class HandoverSection(Contract):
    category: str
    claims: tuple[Claim, ...]


class HandoverSubmissionRequest(Contract):
    resident_id: UUID
    shift_start: AwareDatetime
    shift_end: AwareDatetime

    @model_validator(mode="after")
    def validate_shift_order(self) -> "HandoverSubmissionRequest":
        if self.shift_end <= self.shift_start:
            raise ValueError("shift_end must be after shift_start")

        return self


class HandoverSubmissionResponse(Contract):
    job_id: UUID
    state: HandoverJobState
    status_url: str


class HandoverDraft(Contract):
    job_id: UUID
    draft_id: UUID
    resident_id: UUID
    period: Period

    generated_at: AwareDatetime

    # When retrieval finished; not proof of source freshness.
    retrieved_at: AwareDatetime

    # Set only when the source supplies a meaningful cutoff.
    evidence_cutoff: AwareDatetime | None = None

    coverage_complete: bool
    warnings: tuple[str, ...] = ()
    sections: tuple[HandoverSection, ...]

    agent_version: str
    prompt_version: str
    gateway_version: str
    provider: str
    model_version: str