import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class SearchSourceType(str, Enum):
    FALL = "fall"
    INCIDENT = "incident"
    OBSERVATION = "observation"
    CARE_EVENT = "care_event"
    APPOINTMENT = "appointment"
    CARE_PLAN = "care_plan"


class SearchMode(str, Enum):
    EVIDENCE = "evidence"
    AI_ANSWER = "ai_answer"


class AnswerStatus(str, Enum):
    SUPPORTED = "supported"
    NO_EVIDENCE = "no_evidence"
    PARTIAL = "partial"


class EvidenceCitation(BaseModel):
    evidence_id: str
    source_type: SearchSourceType
    source_id: uuid.UUID
    source_version: datetime | None = None
    occurred_at: datetime
    title: str
    excerpt: str | None = None


class ResidentSearchRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    from_date: datetime | None = Field(default=None, alias="from")
    to_date: datetime | None = Field(default=None, alias="to")
    source_types: list[SearchSourceType] | None = Field(default=None, min_length=1)
    mode: SearchMode = SearchMode.EVIDENCE

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_dates(self):
        if self.from_date and self.to_date and self.from_date >= self.to_date:
            raise ValueError("from_date must be earlier than to_date")
        return self


class ResidentSearchResponse(BaseModel):
    search_id: uuid.UUID
    resident_id: uuid.UUID
    answer: str
    answer_status: AnswerStatus
    coverage_limitations: list[str]
    citations: list[EvidenceCitation]


class ResidentSearchSourceResponse(BaseModel):
    source_type: SearchSourceType
    source_id: uuid.UUID
    occurred_at: datetime
    source_version: datetime | None
    title: str
    details: dict[str, object]
    changed_since_search: bool
