from app.modules.resident_search.evidence.models import EvidenceSourceType
from app.modules.resident_search.registry.models import AuthorityLevel

SOURCE_AUTHORITY = {
    EvidenceSourceType.CARE_PLAN: AuthorityLevel.CARE_PLAN,
    EvidenceSourceType.ASSESSMENT: AuthorityLevel.ASSESSMENT,
    EvidenceSourceType.APPOINTMENT: AuthorityLevel.APPOINTMENT,
    EvidenceSourceType.FALL: AuthorityLevel.INCIDENT,
    EvidenceSourceType.INCIDENT: AuthorityLevel.INCIDENT,
    EvidenceSourceType.CARE_EVENT: AuthorityLevel.CARE_EVENT,
    EvidenceSourceType.OBSERVATION: AuthorityLevel.OBSERVATION,
}