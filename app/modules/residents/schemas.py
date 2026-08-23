import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.modules.residents.models import ResidentStatus


class ResidentCreate(BaseModel):
    """floor_id is required, not just nullable-with-a-default: migration 0013's
    floor-scoped SELECT policy has no `floor_id IS NULL` exception (only INSERT/UPDATE
    do), so a resident created without one can never be read back -- including by the
    very request that creates it, since the ORM's INSERT...RETURNING needs the new row
    to pass the SELECT policy too. NULL is only for pre-existing rows a migration
    backfill hasn't caught up to yet, never for anything the app creates going
    forward."""

    first_name: str
    last_name: str
    date_of_birth: date
    room_number: str
    floor_id: uuid.UUID


class ResidentRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date
    room_number: str | None
    floor_id: uuid.UUID | None
    status: ResidentStatus

    model_config = {"from_attributes": True}


class ResidentSummary(BaseModel):
    """Minimal shape exposed cross-module via ResidentReader -- callers outside
    residents/ never see the full record, just enough to render a name + room."""

    id: uuid.UUID
    display_name: str
    room_number: str | None
    status: ResidentStatus

    model_config = {"from_attributes": True}


class ResidentListItem(BaseModel):
    """GET /residents -- enough for the residents list page to render a card without
    a follow-up request per resident: computed flags/floor name/active care domains
    via ResidentDetailRepository.list_with_summary, not the bare `residents` row
    ResidentRead models."""

    id: uuid.UUID
    first_name: str
    last_name: str
    preferred_name: str | None
    date_of_birth: date
    gender: str | None
    room_number: str | None
    floor_id: uuid.UUID | None
    floor_name: str | None
    status: ResidentStatus
    dnacpr: bool
    has_allergies: bool
    diabetic: bool
    active_care_domains: list[str]
    last_activity_at: datetime | None
    photo_url: str | None


class DiagnosisRead(BaseModel):
    id: uuid.UUID
    condition_name: str
    icd10_code: str | None
    diagnosed_date: date | None
    is_primary: bool
    status: str
    notes: str | None


class AllergyRead(BaseModel):
    id: uuid.UUID
    allergen: str
    reaction: str | None
    severity: str | None


class ContactRead(BaseModel):
    id: uuid.UUID
    full_name: str
    relationship: str
    is_next_of_kin: bool
    is_emergency_contact: bool
    phone: str | None
    email: str | None


class AdvanceDirectiveRead(BaseModel):
    id: uuid.UUID
    directive_type: str
    summary: str
    review_due: date | None
    is_current: bool


class LifeHistoryRead(BaseModel):
    occupation: str | None
    family_background: str | None
    significant_events: str | None
    hobbies_interests: str | None
    important_relationships: str | None
    faith_religion: str | None
    cultural_background: str | None
    military_veteran: bool
    free_text_narrative: str | None


class PreferenceRead(BaseModel):
    category: str
    preference: str
    is_like: bool
    priority: int


class VitalsSnapshot(BaseModel):
    recorded_at: datetime
    blood_pressure_systolic: int | None
    blood_pressure_diastolic: int | None
    heart_rate_bpm: int | None
    oxygen_saturation_pct: int | None
    temperature_celsius: float | None
    news2_score: int | None


class WeightPoint(BaseModel):
    recorded_at: datetime
    weight_kg: float


class ResidentOverview(BaseModel):
    resident_id: uuid.UUID
    diagnoses: list[DiagnosisRead]
    allergies: list[AllergyRead]
    contacts: list[ContactRead]
    advance_directives: list[AdvanceDirectiveRead]
    life_history: LifeHistoryRead | None
    top_preferences: list[PreferenceRead]
    latest_vitals: VitalsSnapshot | None
    weight_trend: list[WeightPoint]
    mobility_level: str | None
    falls_risk_level: str | None
    skin_risk_level: str | None
    active_medication_count: int
    dnacpr: bool


class CarePlanGoalRead(BaseModel):
    id: uuid.UUID
    goal_text: str
    baseline: str | None
    target: str | None
    measurement: str | None
    status: str
    review_date: date | None


class CarePlanRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    domain: str
    goal: str
    is_active: bool
    review_due: date | None
    goals: list[CarePlanGoalRead]


class CareRecordEntry(BaseModel):
    id: uuid.UUID
    record_type: str
    recorded_at: datetime
    title: str
    detail: str | None


class ActivityEntry(BaseModel):
    id: uuid.UUID
    entry_type: str  # 'activity' | 'visit' | 'appointment'
    occurred_at: datetime
    title: str
    detail: str | None
