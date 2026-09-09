import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator

from app import Base


class SummaryFeedbackRating(str, enum.Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


class _FeedbackType(TypeDecorator):
    """Keep the API enum while matching migration 0009's integer feedback column."""

    impl = SmallInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return 1 if SummaryFeedbackRating(value) is SummaryFeedbackRating.THUMBS_UP else -1

    def process_result_value(self, value, dialect):
        if value in (None, 0):
            return None
        return SummaryFeedbackRating.THUMBS_UP if value == 1 else SummaryFeedbackRating.THUMBS_DOWN


class AIOutput(Base):
    """Map the existing ai_outputs schema; retain typed source references verbatim."""

    __tablename__ = "ai_outputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_homes.id"))
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"))
    task: Mapped[str] = mapped_column("output_type", Text, default="daily_summary")
    prompt_template_version: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column("output_text", Text)
    input_record_refs: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_rating: Mapped[SummaryFeedbackRating | None] = mapped_column(_FeedbackType(), nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    @property
    def source_observation_ids(self) -> list[uuid.UUID]:
        """Legacy response field. Use input_record_refs to resolve mixed sources."""
        return [uuid.UUID(ref["id"]) for ref in self.input_record_refs]


__all__ = ["AIOutput", "SummaryFeedbackRating"]
