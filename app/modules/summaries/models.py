import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class SummaryFeedbackRating(str, enum.Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


class AIOutput(Base, TenantMixin):
    """One row per generated summary. `source_observation_ids` is the provenance the
    handover view's "show source records" expander is built on -- never drop it, even
    on regeneration."""

    __tablename__ = "ai_outputs"

    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    task: Mapped[str] = mapped_column(String(100), default="daily_summary")
    prompt_template_version: Mapped[str] = mapped_column(String(20))
    model_version: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    source_observation_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    feedback_rating: Mapped[SummaryFeedbackRating | None] = mapped_column(
        Enum(SummaryFeedbackRating, name="summary_feedback_rating"), nullable=True
    )
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


__all__ = ["AIOutput", "SummaryFeedbackRating"]
