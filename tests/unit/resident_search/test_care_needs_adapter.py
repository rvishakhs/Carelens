import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.modules.resident_search.evidence.care_needs import CareNeedsEvidenceAdapter
from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceSourceType


NOW = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)


def row(**overrides):
    value = {
        "id": uuid.uuid4(),
        "resident_id": uuid.uuid4(),
        "care_home_id": uuid.uuid4(),
        "floor_id": uuid.uuid4(),
        "created_at": NOW,
        "updated_at": NOW,
        "deleted_at": None,
        "effective_from": date(2026, 10, 1),
        "effective_to": None,
        "primary_method": "verbal",
        "hearing_impairment": True,
        "hearing_aid_used": True,
        "visual_impairment": False,
        "glasses_used": False,
        "cognitive_considerations": "Use short sentences.",
        "interpreter_language": None,
        "aac_tools": None,
        "daily_fluid_target_ml": 1500,
        "daily_calorie_target": 1800,
        "toileting_schedule": "Prompt every two hours.",
        "product_regime": "pads",
        "bowel_management_plan": None,
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("source_type", "expected_topic", "expected_title"),
    [
        (EvidenceSourceType.COMMUNICATION_NEED, "communication", "Communication needs"),
        (EvidenceSourceType.NUTRITION_TARGET, "hydration", "Nutrition and hydration target"),
        (EvidenceSourceType.CONTINENCE_CARE_PLAN, "continence", "Continence care plan"),
    ],
)
def test_care_needs_documents_have_concrete_citable_identity(source_type, expected_topic, expected_title):
    adapter = CareNeedsEvidenceAdapter(None, source_type)  # type: ignore[arg-type]
    document = adapter._document(row())

    assert document.evidence_id == f"{source_type.value}:{document.source_id}"
    assert document.authority_level is AuthorityLevel.CARE_NEED
    assert expected_topic in document.topic_tags
    assert document.title == expected_title
    assert document.status == "active"
    assert document.time_precision == "timestamp"


def test_nutrition_target_retains_effective_period_and_numeric_zero():
    adapter = CareNeedsEvidenceAdapter(None, EvidenceSourceType.NUTRITION_TARGET)  # type: ignore[arg-type]
    document = adapter._document(row(daily_fluid_target_ml=0, daily_calorie_target=0, effective_to=date(2026, 12, 1)))

    assert document.effective_from == date(2026, 10, 1)
    assert document.effective_to == date(2026, 12, 1)
    assert "0 ml" in document.searchable_text
    assert "0 kcal" in document.searchable_text


def test_adapter_rejects_non_care_needs_source_type():
    with pytest.raises(ValueError, match="not a care-needs source"):
        CareNeedsEvidenceAdapter(None, EvidenceSourceType.FALL)  # type: ignore[arg-type]


def test_document_rejects_mismatched_source_identity():
    adapter = CareNeedsEvidenceAdapter(None, EvidenceSourceType.COMMUNICATION_NEED)  # type: ignore[arg-type]
    document = adapter._document(row())
    with pytest.raises(ValidationError, match="evidence_id"):
        document.model_validate({**document.model_dump(), "evidence_id": f"communication_need:{uuid.uuid4()}"})
