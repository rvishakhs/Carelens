from app.modules.resident_search.evidence.models import EvidenceSourceType

PERSISTED_CITATION_SOURCE_TYPES = frozenset({
    EvidenceSourceType.CARE_PLAN,
    EvidenceSourceType.CARE_EVENT,
    EvidenceSourceType.FALL,
    EvidenceSourceType.APPOINTMENT,
    EvidenceSourceType.INCIDENT,
    EvidenceSourceType.OBSERVATION,
    EvidenceSourceType.SLEEP,
    EvidenceSourceType.NUTRITION,
    EvidenceSourceType.MOBILITY,
    EvidenceSourceType.WELLBEING,
    EvidenceSourceType.COMMUNICATION,
    EvidenceSourceType.WOUND,
    EvidenceSourceType.MOBILITY_ASSESSMENT,
    EvidenceSourceType.NUTRITION_ASSESSMENT,
    EvidenceSourceType.SKIN_ASSESSMENT,
    EvidenceSourceType.MENTAL_HEALTH_ASSESSMENT,
    EvidenceSourceType.COMMUNICATION_NEED,
    EvidenceSourceType.NUTRITION_TARGET,
    EvidenceSourceType.CONTINENCE_CARE_PLAN,
})
