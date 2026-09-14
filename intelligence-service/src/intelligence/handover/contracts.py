# src/intelligence/handover/contracts.py

from uuid import UUID

from pydantic import AwareDatetime

from intelligence.core.contracts import Claim, Contract, Period


class HandoverSection(Contract):
    category: str
    claims: tuple[Claim, ...]


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