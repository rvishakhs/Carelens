from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentId(StrEnum):
    HISTORY = "resident_history"
    HANDOVER = "handover_draft"


class Scope(Contract):
    tenant_id: UUID
    actor_id: UUID
    resident_ids: frozenset[UUID]
    permissions: frozenset[str]


class Period(Contract):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def ordered(self) -> "Period":
        if self.start >= self.end:
            raise ValueError("start must precede end")
        if (self.end - self.start).total_seconds() > 31 * 86400:
            raise ValueError("synthetic skeleton supports periods up to 31 days")
        return self


class RunRequest(Contract):
    agent_id: AgentId
    resident_id: UUID
    period: Period
    question: str = Field(default="Summarise the recorded care", min_length=1, max_length=1000)


class SourceRef(Contract):
    source_system: Literal["synthetic"] = "synthetic"
    source_type: str
    source_id: UUID
    version: str


class Evidence(Contract):
    tenant_id: UUID
    resident_id: UUID
    reference: SourceRef
    effective_at: AwareDatetime
    recorded_at: AwareDatetime
    time_basis: Literal["effective", "recorded"] = "effective"
    kind: Literal["fluid", "care"]
    consumed_ml: int | None = Field(default=None, ge=0)
    offered_ml: int | None = Field(default=None, ge=0)


class EvidenceBundle(Contract):
    records: tuple[Evidence, ...]
    retrieved_at: AwareDatetime
    complete: bool
    warnings: tuple[str, ...] = ()


class Claim(Contract):
    text: str
    sources: tuple[SourceRef, ...]


class RunResult(Contract):
    run_id: UUID = Field(default_factory=uuid4)
    agent_id: AgentId
    resident_id: UUID
    period: Period
    state: Literal["completed", "draft"]
    synthetic: Literal[True] = True
    provider: Literal["fake"] = "fake"
    agent_version: str = "0.1.0"
    gateway_version: str = "synthetic-structured-v1"
    generated_at: datetime
    data_cutoff: datetime
    coverage_complete: bool
    claims: tuple[Claim, ...]
    warnings: tuple[str, ...]
