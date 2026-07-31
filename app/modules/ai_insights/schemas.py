import uuid
from datetime import datetime

from pydantic import BaseModel


class ResidentAISummaryRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    summary_type: str
    period_start: datetime
    period_end: datetime
    summary_text: str
    is_current: bool
    feedback_rating: int | None
    feedback_comment: str | None
    generated_at: datetime

    model_config = {"from_attributes": True}


class ResidentAIReportRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    report_domain: str
    period_start: datetime
    period_end: datetime
    report_text: str
    structured_findings: dict
    is_current: bool
    generated_at: datetime

    model_config = {"from_attributes": True}


class ResidentAIAlertRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    alert_type: str
    severity: str
    alert_text: str
    status: str
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    resolution_note: str | None
    generated_at: datetime

    model_config = {"from_attributes": True}


class ResidentPredictionRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    prediction_type: str
    horizon_days: int | None
    confidence: float | None
    prediction_text: str
    recommended_action: str | None
    status: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class SummaryFeedbackCreate(BaseModel):
    rating: int  # -1 | 0 | 1
    comment: str | None = None


class AlertAcknowledgeRequest(BaseModel):
    resolution_note: str | None = None
