from enum import IntEnum, Enum

from app.modules.resident_search.evidence.models import EvidenceSourceType
from pydantic import BaseModel


class AuthorityLevel(IntEnum):
    OBSERVATION = 50
    CARE_EVENT = 60
    APPOINTMENT = 75
    INCIDENT = 75
    CARE_NEED = 85
    ASSESSMENT = 90
    CARE_PLAN = 100


class ResidentSearchIntent(str, Enum):
    MOBILITY_REQUIREMENT = "mobility_requirement"
    NUTRITION_NEED = "nutrition_need"
    COMMUNICATION_NEED = "communication_need"
    FALL_HISTORY = "fall_history"
    APPOINTMENT_HISTORY = "appointment_history"
    SLEEP_PATTERN = "sleep_pattern"
    SKIN_WOUND_STATUS = "skin_wound_status"
    WELLBEING_CONCERN = "wellbeing_concern"



class IntentSourceRule(BaseModel):
    source_type: EvidenceSourceType
    authority_level: AuthorityLevel
    topics: frozenset[str] = frozenset()
    current_only: bool = False
    required: bool = False
    maximum_results: int = 10