import uuid
from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
