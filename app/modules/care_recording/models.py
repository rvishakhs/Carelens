"""ORM models for the metadata-driven care template + event engine
(migrations/versions/0014). Deliberately doesn't reuse TenantMixin: care_home_id is
NULLABLE on every template-config table (NULL = global template, shared across every
home) and the event child tables (options/measurements/files) don't carry
updated_at/deleted_at the way TenantMixin assumes -- the heterogeneity is real, not
an oversight, so each model spells out its own columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.shared.database import Base


class CareCategory(Base):
    """System-wide reference data (no care_home_id, no RLS) -- same treatment as an
    enum catalog table. See migrations/versions/0014's own comment."""

    __tablename__ = "care_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CareTemplate(Base):
    __tablename__ = "care_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # NULL = global
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_categories.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_note: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sections: Mapped[list["CareTemplateSection"]] = relationship(order_by="CareTemplateSection.sort_order")
    measurements: Mapped[list["CareTemplateMeasurement"]] = relationship(order_by="CareTemplateMeasurement.sort_order")


class CareTemplateSection(Base):
    __tablename__ = "care_template_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_templates.id"))
    name: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    allow_multiple: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    options: Mapped[list["CareTemplateOption"]] = relationship(order_by="CareTemplateOption.sort_order")


class CareTemplateOption(Base):
    __tablename__ = "care_template_options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_template_sections.id"))
    label: Mapped[str] = mapped_column(String(255))
    value_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    requires_note: Mapped[bool] = mapped_column(Boolean, default=False)
    triggers_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CareTemplateMeasurement(Base):
    __tablename__ = "care_template_measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_templates.id"))
    name: Mapped[str] = mapped_column(String(255))
    data_type: Mapped[str] = mapped_column(String(20))  # 'numeric' | 'text' | 'boolean' (DB CHECK, not an enum type)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    min_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CareEvent(Base):
    """One carer's tap-through of a template, for one resident. floor_id is
    auto-filled from the resident by a DB trigger (sync_floor_id_from_resident) if the
    app doesn't supply it -- see migrations/versions/0014."""

    __tablename__ = "care_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    floor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("floors.id"), nullable=True)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_templates.id"))
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_categories.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")  # completed|declined|refused|not_applicable
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CareEventOption(Base):
    __tablename__ = "care_event_options"
    __table_args__ = (UniqueConstraint("care_event_id", "care_template_option_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    floor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("floors.id"), nullable=True)
    care_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_events.id"))
    care_template_option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("care_template_options.id")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CareEventMeasurement(Base):
    __tablename__ = "care_event_measurements"
    __table_args__ = (UniqueConstraint("care_event_id", "care_template_measurement_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    floor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("floors.id"), nullable=True)
    care_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_events.id"))
    care_template_measurement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("care_template_measurements.id")
    )
    value_numeric: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CareEventFile(Base):
    __tablename__ = "care_event_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    floor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("floors.id"), nullable=True)
    care_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("care_events.id"))
    file_url: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "CareCategory",
    "CareTemplate",
    "CareTemplateSection",
    "CareTemplateOption",
    "CareTemplateMeasurement",
    "CareEvent",
    "CareEventOption",
    "CareEventMeasurement",
    "CareEventFile",
]
