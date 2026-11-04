import uuid
from datetime import datetime, date
from enum import Enum, IntEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator


class EvidenceSourceType(str, Enum):
    FALL = "fall"
    INCIDENT = "incident"
    OBSERVATION = "observation"
    CARE_EVENT = "care_event"
    APPOINTMENT = "appointment"
    CARE_PLAN = "care_plan"
    MEDICATION = "medication"
    WELLBEING = "wellbeing"
    MOBILITY = "mobility"
    NUTRITION = "nutrition"
    COMMUNICATION = "communication"
    SLEEP = "sleep"
    WOUND = "wound"

    SOURCE_GROUP= "assessment"
    MOBILITY_ASSESSMENT = "mobility_assessment"
    NUTRITION_ASSESSMENT = "nutrition_assessment"
    SKIN_ASSESSMENT = "skin_assessment"
    MENTAL_HEALTH_ASSESSMENT = "mental_health_assessment"
    COMMUNICATION_NEED = "communication_need"
    NUTRITION_TARGET = "nutrition_target"
    CONTINENCE_CARE_PLAN = "continence_care_plan"



class AuthorityLevel(IntEnum):
    CARE_PLAN = 100
    FORMAL_ASSESSMENT = 90
    CARE_NEED = 85
    STRUCTURED_INCIDENT = 75
    APPOINTMENT = 75
    CARE_EVENT = 60
    OBSERVATION = 50
    HISTORICAL = 25

class EvidenceDocument(BaseModel):
    """Internal retrieval shape"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    resident_id: uuid.UUID
    care_home_id: uuid.UUID
    floor_id: uuid.UUID
    authority_level: AuthorityLevel  # care_plan, assessment, incident, care_event, observation

    source_type: EvidenceSourceType
    source_id: uuid.UUID
    source_version: datetime | str   # must reflect child-record changes too

    topic_tags: set[str]
    status: str | None               # active, approved, completed, cancelled...
    occurred_at: datetime | None
    time_precision: Literal["timestamp", "date", "effective_period"]
    effective_from: date | None
    effective_to: date | None

    title: str
    searchable_text: str
    structured_metadata: dict
    is_deleted: bool
    is_eligible: bool


    @model_validator(mode="after")
    def validate_evidence_id(self) -> "EvidenceDocument":
        if self.evidence_id != f"{self.source_type.value}:{self.source_id}":
            raise ValueError("evidence_id must match source_type and source_id")
        return self
