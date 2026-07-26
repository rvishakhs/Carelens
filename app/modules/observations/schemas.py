import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, model_validator

from app.modules.observations.models import ObservationType

# Clinical safety starts at input validation: implausible values are flagged, not
# silently accepted -- but never rejected outright, since a false-negative bound would
# block a carer from recording something real. See governance/hazard-log.md.
_PLAUSIBILITY_BOUNDS: dict[ObservationType, dict[str, tuple[float, float]]] = {
    ObservationType.FLUID_INTAKE: {"ml": (0, 2000)},
    ObservationType.WEIGHT: {"kg": (20, 250)},
    ObservationType.VITALS: {
        "heart_rate_bpm": (30, 220),
        "systolic_bp": (60, 250),
        "diastolic_bp": (30, 150),
        "temperature_c": (30, 43),
        "spo2_pct": (50, 100),
    },
}


def is_plausible(observation_type: ObservationType, value: dict[str, Any]) -> bool:
    bounds = _PLAUSIBILITY_BOUNDS.get(observation_type, {})
    for field, (low, high) in bounds.items():
        if field in value:
            reading = value[field]
            if not isinstance(reading, int | float) or not (low <= reading <= high):
                return False
    return True


class ObservationCreate(BaseModel):
    resident_id: uuid.UUID
    type: ObservationType
    value: dict[str, Any]
    recorded_at: datetime
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def note_requires_text(self) -> "ObservationCreate":
        if self.type is ObservationType.NOTE and not isinstance(self.value.get("text"), str):
            raise ValueError("note observations require value.text")
        return self


class ObservationRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    type: ObservationType
    value: dict[str, Any]
    recorded_at: datetime
    recorded_by: uuid.UUID
    is_implausible: bool

    model_config = {"from_attributes": True}


class ObservationSummary(BaseModel):
    """Cross-module read shape via ObservationReader -- structured data only, no note
    free-text, so consumers like summaries/handover don't need pseudonymisation
    reasoning duplicated at the call site."""

    id: uuid.UUID
    resident_id: uuid.UUID
    type: ObservationType
    value: dict[str, Any]
    recorded_at: datetime
    is_implausible: bool

    model_config = {"from_attributes": True}
