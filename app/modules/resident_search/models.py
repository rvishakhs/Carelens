import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app import Base

class ResidentHistorySearch(Base):
    __tablename__ = "resident_history_searches"

    __table_args__ = (
        CheckConstraint(
            "mode IN ('evidence', 'ai_answer')",
            name="ck_resident_history_search_mode",
        ),
        CheckConstraint(
            "answer_status IN ('supported', 'no_evidence', 'partial')",
            name="ck_resident_history_search_answer_status",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_resident_history_search_expiry",
        ),
        UniqueConstraint(
            "id",
            "care_home_id",
            "floor_id",
            "resident_id",
            name="uq_resident_history_search_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    care_home_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("care_homes.id"),
        nullable=False,
    )
    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.id"),
        nullable=False,
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id"),
        nullable=False,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Stored as TEXT in PostgreSQL, constrained by the migration.
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    answer: Mapped[str] = mapped_column(String, nullable=False)
    answer_status: Mapped[str] = mapped_column(String(20), nullable=False)

    coverage_limitations: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    citations: Mapped[list["ResidentHistorySearchCitation"]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
        order_by="ResidentHistorySearchCitation.rank",
    )


class ResidentHistorySearchCitation(Base):
    __tablename__ = "resident_history_search_citations"

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('fall', 'incident', 'observation', "
            "'care_event', 'appointment', 'care_plan')",
            name="ck_resident_history_search_citation_source_type",
        ),
        CheckConstraint(
            "rank > 0",
            name="ck_resident_history_search_citation_rank",
        ),
        ForeignKeyConstraint(
            ["search_id", "care_home_id", "floor_id", "resident_id"],
            [
                "resident_history_searches.id",
                "resident_history_searches.care_home_id",
                "resident_history_searches.floor_id",
                "resident_history_searches.resident_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "search_id",
            "source_type",
            "source_id",
            name="uq_resident_history_search_citation_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    search_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Duplicated deliberately: this allows RLS to protect each citation directly.
    care_home_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("care_homes.id"),
        nullable=False,
    )
    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.id"),
        nullable=False,
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id"),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_version: Mapped[datetime | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    search: Mapped[ResidentHistorySearch] = relationship(
        back_populates="citations",
    )
