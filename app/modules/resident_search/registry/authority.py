from app.modules.resident_search.evidence.models import EvidenceSourceType, AuthorityLevel

SOURCE_AUTHORITY = {
    EvidenceSourceType.CARE_PLAN: AuthorityLevel.CARE_PLAN,
    EvidenceSourceType.ASSESSMENT: AuthorityLevel.FORMAL_ASSESSMENT,
    EvidenceSourceType.APPOINTMENT: AuthorityLevel.APPOINTMENT,
    EvidenceSourceType.FALL: AuthorityLevel.STRUCTURED_INCIDENT,
    EvidenceSourceType.INCIDENT: AuthorityLevel.STRUCTURED_INCIDENT,
    EvidenceSourceType.CARE_EVENT: AuthorityLevel.CARE_EVENT,
    EvidenceSourceType.COMMUNICATION_NEED: AuthorityLevel.CARE_NEED,
    EvidenceSourceType.NUTRITION_TARGET: AuthorityLevel.CARE_NEED,
    EvidenceSourceType.CONTINENCE_CARE_PLAN: AuthorityLevel.CARE_NEED,
    EvidenceSourceType.OBSERVATION: AuthorityLevel.OBSERVATION,
}
