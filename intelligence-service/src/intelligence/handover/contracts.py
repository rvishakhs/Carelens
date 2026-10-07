from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from intelligence.core.contracts import Claim, Contract, Period, ExecutionContext
from intelligence.handover.evidence import ShiftEvidence
from intelligence.handover.metrics import HandoverMetrics


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

class GenerationMetadata(Contract):
    agent_version: str
    prompt_version: str
    gateway_version: str
    provider: str
    model_version: str
    generated_at: AwareDatetime


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

class HandoverStatusResponse(Contract):
    job_id: UUID
    resident_id: UUID
    state: HandoverJobState
    shift_start: AwareDatetime
    shift_end: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime


###### Agent Geteway COntracts ##########

class HandoverRetrieval(Contract):
    """Internal evidence and metadata from the retrieval stage."""

    evidence: ShiftEvidence

    # When the connector finished retrieving records.
    retrieved_at: AwareDatetime

    # Only populated when supported by the source system.
    evidence_cutoff: AwareDatetime | None = None

    # Required explicitly: fetching every page does not prove
    # complete coverage of every required source.
    coverage_complete: bool

    warnings: tuple[str, ...] = ()


class HandoverAgentInput(Contract):
    """Trusted internal input; must never be sent to the provider."""

    execution_context: ExecutionContext

    job_id: UUID
    resident_id: UUID

    period: Period
    care_home_timezone: str

    retrieval: HandoverRetrieval
    metrics: HandoverMetrics


class ValidatedHandoverContent(Contract):
    """Gateway output with resolved internal source references.

    Validation here does not mean clinical approval.
    Nurse review remains required.
    """

    sections: tuple[HandoverSection, ...]

    # Preserved by trusted code, independently of model output.
    warnings: tuple[str, ...] = ()

    coverage_complete: bool
