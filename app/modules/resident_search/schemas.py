import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, BeforeValidator, Field, model_validator

from app.modules.resident_search.evidence.models import EvidenceSourceType
from app.modules.resident_search.evidence.revisions import revision_token

# Compatibility for existing callers; the canonical enum lives in evidence/models.py.
SearchSourceType = EvidenceSourceType
SourceRevision = Annotated[str | None, BeforeValidator(revision_token)]


class SearchMode(str, Enum):
    EVIDENCE = "evidence"
    AI_ANSWER = "ai_answer"


class AnswerStatus(str, Enum):
    SUPPORTED = "supported"
    NO_EVIDENCE = "no_evidence"
    PARTIAL = "partial"


class EvidenceCitation(BaseModel):
    evidence_id: str
    source_type: EvidenceSourceType
    source_id: uuid.UUID
    source_version: SourceRevision = None
    occurred_at: datetime
    title: str
    excerpt: str | None = None


class ResidentSearchRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500, pattern=r"\S")
    from_date: AwareDatetime | None = Field(default=None, alias="from")
    to_date: AwareDatetime | None = Field(default=None, alias="to")
    source_types: list[EvidenceSourceType] | None = Field(default=None, min_length=1)
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
    source_type: EvidenceSourceType
    source_id: uuid.UUID
    occurred_at: datetime
    source_version: SourceRevision
    title: str
    details: dict[str, object]
    changed_since_search: bool
