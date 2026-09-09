import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app import SummaryFeedbackRating


class SummaryRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    content: str
    prompt_template_version: str
    model_version: str
    source_observation_ids: list[uuid.UUID]
    input_record_refs: list[dict[str, str]] = Field(default_factory=list)
    generated_at: datetime
    feedback_rating: SummaryFeedbackRating | None
    feedback_comment: str | None

    model_config = {"from_attributes": True}


class SummaryFeedbackCreate(BaseModel):
    rating: SummaryFeedbackRating
    comment: str | None = None
