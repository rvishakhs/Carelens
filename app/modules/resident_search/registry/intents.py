"""Approved retrieval plans for the future resident-search orchestrator.

This module does not classify questions or call adapters.  It merely constrains
the sources a later deterministic intent router may ask for.
"""

from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceSourceType
from app.modules.resident_search.registry.models import IntentSourceRule, ResidentSearchIntent


def _rule(
    source_type: EvidenceSourceType,
    authority_level: AuthorityLevel,
    *topics: str,
    current_only: bool = False,
    required: bool = False,
) -> IntentSourceRule:
    return IntentSourceRule(
        source_type=source_type,
        authority_level=authority_level,
        topics=frozenset(topics),
        current_only=current_only,
        required=required,
    )


INTENT_SOURCES: dict[ResidentSearchIntent, tuple[IntentSourceRule, ...]] = {
    ResidentSearchIntent.MOBILITY_REQUIREMENT: (
        _rule(EvidenceSourceType.CARE_PLAN, AuthorityLevel.CARE_PLAN, "mobility", "transfer", current_only=True, required=True),
        _rule(EvidenceSourceType.MOBILITY_ASSESSMENT, AuthorityLevel.FORMAL_ASSESSMENT, "mobility", "transfer", current_only=True, required=True),
        _rule(EvidenceSourceType.CARE_EVENT, AuthorityLevel.CARE_EVENT, "mobility", "transfer"),
        _rule(EvidenceSourceType.FALL, AuthorityLevel.STRUCTURED_INCIDENT, "mobility", "fall"),
        _rule(EvidenceSourceType.MOBILITY, AuthorityLevel.OBSERVATION, "mobility", "transfer"),
    ),
    ResidentSearchIntent.NUTRITION_NEED: (
        _rule(EvidenceSourceType.CARE_PLAN, AuthorityLevel.CARE_PLAN, "nutrition", "hydration", current_only=True, required=True),
        _rule(EvidenceSourceType.NUTRITION_TARGET, AuthorityLevel.CARE_NEED, "nutrition", "hydration", current_only=True, required=True),
        _rule(EvidenceSourceType.NUTRITION_ASSESSMENT, AuthorityLevel.FORMAL_ASSESSMENT, "nutrition", "hydration", current_only=True),
        _rule(EvidenceSourceType.CARE_EVENT, AuthorityLevel.CARE_EVENT, "nutrition", "hydration"),
        _rule(EvidenceSourceType.NUTRITION, AuthorityLevel.OBSERVATION, "nutrition", "hydration"),
    ),
    ResidentSearchIntent.COMMUNICATION_NEED: (
        _rule(EvidenceSourceType.COMMUNICATION_NEED, AuthorityLevel.CARE_NEED, "communication", current_only=True, required=True),
        _rule(EvidenceSourceType.CARE_PLAN, AuthorityLevel.CARE_PLAN, "communication", current_only=True),
        _rule(EvidenceSourceType.CARE_EVENT, AuthorityLevel.CARE_EVENT, "communication"),
        _rule(EvidenceSourceType.COMMUNICATION, AuthorityLevel.OBSERVATION, "communication"),
    ),
    ResidentSearchIntent.FALL_HISTORY: (
        _rule(EvidenceSourceType.FALL, AuthorityLevel.STRUCTURED_INCIDENT, "fall", required=True),
        _rule(EvidenceSourceType.CARE_EVENT, AuthorityLevel.CARE_EVENT, "fall"),
        _rule(EvidenceSourceType.OBSERVATION, AuthorityLevel.OBSERVATION, "fall", "mobility"),
    ),
    ResidentSearchIntent.APPOINTMENT_HISTORY: (
        _rule(EvidenceSourceType.APPOINTMENT, AuthorityLevel.APPOINTMENT, "appointment", required=True),
        _rule(EvidenceSourceType.CARE_EVENT, AuthorityLevel.CARE_EVENT, "appointment"),
    ),
    ResidentSearchIntent.SLEEP_PATTERN: (
        _rule(EvidenceSourceType.SLEEP, AuthorityLevel.OBSERVATION, "sleep", required=True),
        _rule(EvidenceSourceType.CARE_EVENT, AuthorityLevel.CARE_EVENT, "sleep"),
    ),
    ResidentSearchIntent.SKIN_WOUND_STATUS: (
        _rule(EvidenceSourceType.SKIN_ASSESSMENT, AuthorityLevel.FORMAL_ASSESSMENT, "skin", "repositioning", current_only=True, required=True),
        _rule(EvidenceSourceType.WOUND, AuthorityLevel.OBSERVATION, "wound", "skin"),
        _rule(EvidenceSourceType.CARE_PLAN, AuthorityLevel.CARE_PLAN, "skin", "repositioning", current_only=True),
    ),
    ResidentSearchIntent.WELLBEING_CONCERN: (
        _rule(EvidenceSourceType.MENTAL_HEALTH_ASSESSMENT, AuthorityLevel.FORMAL_ASSESSMENT, "wellbeing", "behaviour", current_only=True),
        _rule(EvidenceSourceType.WELLBEING, AuthorityLevel.OBSERVATION, "wellbeing", "behaviour", required=True),
        _rule(EvidenceSourceType.CARE_EVENT, AuthorityLevel.CARE_EVENT, "wellbeing", "behaviour"),
    ),
}


def sources_for_intent(intent: ResidentSearchIntent) -> tuple[IntentSourceRule, ...]:
    return INTENT_SOURCES[intent]
