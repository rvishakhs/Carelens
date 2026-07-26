import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.summaries.models import SummaryFeedbackRating


class SummaryRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    content: str
    prompt_template_version: str
    model_version: str
    source_observation_ids: list[uuid.UUID]
    generated_at: datetime
    feedback_rating: SummaryFeedbackRating | None
    feedback_comment: str | None

    model_config = {"from_attributes": True}


class SummaryFeedbackCreate(BaseModel):
    rating: SummaryFeedbackRating
    comment: str | None = None
