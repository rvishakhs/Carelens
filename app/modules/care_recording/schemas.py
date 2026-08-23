import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CareCategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    icon: str | None
    sort_order: int

    model_config = {"from_attributes": True}


class CareTemplateOptionRead(BaseModel):
    id: uuid.UUID
    label: str
    value_code: str | None
    sort_order: int
    requires_note: bool
    triggers_alert: bool

    model_config = {"from_attributes": True}


class CareTemplateSectionRead(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    allow_multiple: bool
    options: list[CareTemplateOptionRead] = []

    model_config = {"from_attributes": True}


class CareTemplateMeasurementRead(BaseModel):
    id: uuid.UUID
    name: str
    data_type: str
    unit: str | None
    min_value: float | None
    max_value: float | None
    is_required: bool

    model_config = {"from_attributes": True}


class CareTemplateRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    requires_note: bool
    sort_order: int
    sections: list[CareTemplateSectionRead] = []
    measurements: list[CareTemplateMeasurementRead] = []

    model_config = {"from_attributes": True}


class CareEventOptionCreate(BaseModel):
    care_template_option_id: uuid.UUID
    note: str | None = None


class CareEventMeasurementCreate(BaseModel):
    care_template_measurement_id: uuid.UUID
    value_numeric: float | None = None
    value_text: str | None = None
    value_boolean: bool | None = None


class CareEventCreate(BaseModel):
    resident_id: uuid.UUID
    template_id: uuid.UUID
    occurred_at: datetime | None = None  # defaults to now() at the DB if omitted
    status: str = "completed"  # completed | declined | refused | not_applicable
    note: str | None = None
    # Required, not just DB-nullable (migration 0021): staff time spent on this
    # entry, so resident-level human-resource-need reporting has something to sum.
    duration_minutes: int = Field(gt=0)
    options: list[CareEventOptionCreate] = []
    measurements: list[CareEventMeasurementCreate] = []


class CareEventRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    template_id: uuid.UUID
    category_id: uuid.UUID
    occurred_at: datetime
    recorded_by: uuid.UUID | None
    status: str
    note: str | None
    duration_minutes: int | None
    summary: str | None

    model_config = {"from_attributes": True}


class CareEventOptionSummary(BaseModel):
    label: str
    note: str | None


class CareEventMeasurementSummary(BaseModel):
    name: str
    unit: str | None
    value_numeric: float | None
    value_text: str | None
    value_boolean: bool | None


class CareEventHistoryItem(BaseModel):
    """GET /care-recording/residents/{id}/events -- denormalised for the resident's
    Care Records tile view: template/category names and the option labels + measurement
    values actually recorded, so the tile grid and its expanded detail don't need a
    per-event follow-up request."""

    id: uuid.UUID
    template_name: str
    category_name: str
    category_icon: str | None
    occurred_at: datetime
    status: str
    note: str | None
    summary: str | None
    duration_minutes: int | None
    recorded_by_name: str | None
    options: list[CareEventOptionSummary] = []
    measurements: list[CareEventMeasurementSummary] = []
