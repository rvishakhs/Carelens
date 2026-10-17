
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


class ResidentSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    from_date: datetime | None = None
    to_date: datetime | None = None
    source_types: list[SearchSourceType] | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.from_date and self.to_date and self.from_date >= self.to_date:
            raise ValueError("from_date must be earlier than to_date")
        return self


class EvidenceCitation(BaseModel):
    evidence_id: str
    source_type: SearchSourceType
    source_id: uuid.UUID
    occurred_at: datetime
    title: str
    excerpt: str | None = None


class ResidentSearchResponse(BaseModel):
    resident_id: uuid.UUID
    query: str
    result_summary: str
    evidence: list[EvidenceCitation]
    coverage_limitations: list[str] = []