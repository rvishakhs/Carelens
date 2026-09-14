from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4
from datetime import date,datetime ,time

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
    source_system: Literal["synthetic", "Carelens_connector"] = "synthetic"
    source_type: str
    source_id: UUID
    version: str
    # Fingerprint will help to indentify the changes after the draft is made
    fingerprint: str | None = None

class ExecutionContext(Contract):
    tenant_id: UUID

    # Set for a manual request; absent for a scheduled request.
    initiating_actor_id: UUID | None = None

    # Identity of the service executing the job.
    service_identity: str

    trigger: Literal["manual", "scheduled"]
    purpose: Literal["handover_generation"] = "handover_generation"

    authorised_resident_ids: frozenset[UUID]
    permissions: frozenset[str]

    @model_validator(mode="after")
    def validate_actor(self) -> "ExecutionContext":
        if self.trigger == "manual" and self.initiating_actor_id is None:
            raise ValueError("manual execution requires initiating_actor_id")

        if self.trigger == "scheduled" and self.initiating_actor_id is not None:
            raise ValueError("scheduled execution must not impersonate a staff member")

        return self

class Evidence(Contract):
    tenant_id: UUID
    resident_id: UUID
    reference: SourceRef

    effective_at: AwareDatetime | None = None
    source_date: date | None = None
    recorded_at: AwareDatetime | None = None

    time_basis: Literal["effective", "recorded", "unknown"]
    time_precision: Literal["timestamp", "date", "unknown"]

    kind: str


    consumed_ml: int | None = Field(default=None, ge=0)
    offered_ml: int | None = Field(default=None, ge=0)

    # Internal clinical narrative; NOT safe to send directly to a model.
    narrative: str | None = None

    @model_validator(mode="after")
    def validate_time(self) -> "Evidence":
        if self.time_precision == "date":
            if self.source_date is None or self.effective_at is not None:
                raise ValueError(
                    "date-only evidence requires source_date "
                    "and must not invent an effective timestamp"
                )

        if self.time_precision == "timestamp":
            if self.time_basis == "effective" and self.effective_at is None:
                raise ValueError("effective timestamp is required")

            if self.time_basis == "recorded" and self.recorded_at is None:
                raise ValueError("recorded timestamp is required")

            if self.time_basis == "unknown":
                raise ValueError("timestamp evidence requires a known time basis")

        return self


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
