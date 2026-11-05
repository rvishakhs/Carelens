import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.modules.resident_search.evidence.assessments.adapter import AssessmentEvidenceAdapter
from app.modules.resident_search.evidence.assessments.mental_health import MentalHealthAssessmentReader
from app.modules.resident_search.evidence.assessments.mobility import MobilityAssessmentReader
from app.modules.resident_search.evidence.assessments.nutrition import NutritionAssessmentReader
from app.modules.resident_search.evidence.assessments.skin import SkinAssessmentReader
from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceDocument, EvidenceSourceType


def assessment_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "resident_id": uuid.uuid4(),
        "care_home_id": uuid.uuid4(),
        "floor_id": uuid.uuid4(),
        "assessment_tool": "Example tool",
        "assessed_at": datetime(2026, 10, 24, 10, tzinfo=UTC),
        "next_review_due": None,
        "created_at": datetime(2026, 10, 24, 10, tzinfo=UTC),
        "deleted_at": None,
    }
    return row | overrides


def test_mobility_assessment_normalises_authoritative_fields():
    row = assessment_row(
        mobility_level="assisted",
        aids_used=["standing_aid"],
        transfer_method="standing hoist",
        falls_risk_score=7,
        falls_risk_level="high",
        notes="Private local note",
    )

    document = MobilityAssessmentReader._document(row)

    assert document.evidence_id == f"mobility_assessment:{row['id']}"
    assert document.source_type is EvidenceSourceType.MOBILITY_ASSESSMENT
    assert document.authority_level is AuthorityLevel.FORMAL_ASSESSMENT
    assert document.structured_metadata["transfer_method"] == "standing hoist"
    assert "Private local note" not in document.searchable_text


def test_nutrition_assessment_keeps_scores_as_values_not_tuples():
    row = assessment_row(
        assessment_tool="MUST",
        bmi_score=1,
        weight_loss_score=2,
        acute_disease_score=0,
        total_score=3,
        risk_level="high",
        action_plan="Weekly weight monitoring",
    )

    document = NutritionAssessmentReader._document(row)

    assert document.source_type is EvidenceSourceType.NUTRITION_ASSESSMENT
    assert document.structured_metadata["weight_loss_score"] == 2
    assert not isinstance(document.structured_metadata["weight_loss_score"], tuple)
    assert "Recorded action plan: Weekly weight monitoring" in document.searchable_text


def test_skin_assessment_normalises_pressure_area_list_and_repositioning():
    row = assessment_row(
        assessment_tool="Waterlow",
        total_score=17,
        risk_level="high",
        pressure_areas_checked=["sacrum", "heels"],
        equipment_in_use="Pressure-relieving mattress",
        reposition_frequency="every 2 hours",
    )

    document = SkinAssessmentReader._document(row)

    assert document.source_type is EvidenceSourceType.SKIN_ASSESSMENT
    assert "Pressure areas checked: sacrum, heels." in document.searchable_text
    assert "Recorded repositioning frequency: every 2 hours." in document.searchable_text


def test_mental_health_assessment_uses_its_own_source_identity_and_label():
    row = assessment_row(
        assessment_tool="GDS",
        total_score=8,
        interpretation="Further review required",
    )

    document = MentalHealthAssessmentReader._document(row)

    assert document.evidence_id == f"mental_health_assessment:{row['id']}"
    assert document.source_type is EvidenceSourceType.MENTAL_HEALTH_ASSESSMENT
    assert document.title == "Mental health assessment"
    assert "GDS mental-health assessment." in document.searchable_text
    assert "nutrition" not in document.searchable_text.casefold()


def document(source_type: EvidenceSourceType, occurred_at: datetime) -> EvidenceDocument:
    source_id = uuid.uuid4()
    return EvidenceDocument(
        evidence_id=f"{source_type.value}:{source_id}",
        source_type=source_type,
        source_id=source_id,
        resident_id=uuid.uuid4(),
        care_home_id=uuid.uuid4(),
        floor_id=uuid.uuid4(),
        authority_level=AuthorityLevel.FORMAL_ASSESSMENT,
        topic_tags={"assessment"},
        status="assessed",
        occurred_at=occurred_at,
        time_precision="timestamp",
        effective_from=None,
        effective_to=None,
        source_version=occurred_at,
        title="Assessment",
        searchable_text="Assessment.",
        structured_metadata={},
        is_deleted=False,
        is_eligible=True,
    )


class StubReader:
    def __init__(self, documents: list[EvidenceDocument]):
        self.documents = documents
        self.find_calls: list[dict] = []
        self.get_calls: list[dict] = []

    async def find(self, **kwargs):
        self.find_calls.append(kwargs)
        return self.documents

    async def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return next((item for item in self.documents if item.source_id == kwargs["source_id"]), None)


async def test_assessment_adapter_combines_sorts_and_dispatches_concrete_sources():
    adapter = AssessmentEvidenceAdapter(SimpleNamespace())
    resident_id = uuid.uuid4()
    earlier = document(EvidenceSourceType.MOBILITY_ASSESSMENT, datetime(2026, 10, 20, tzinfo=UTC))
    later = document(EvidenceSourceType.SKIN_ASSESSMENT, datetime(2026, 10, 24, tzinfo=UTC))
    earlier = earlier.model_copy(update={"resident_id": resident_id})
    later = later.model_copy(update={"resident_id": resident_id})
    mobility = StubReader([earlier])
    skin = StubReader([later])
    adapter._readers = {
        EvidenceSourceType.MOBILITY_ASSESSMENT: mobility,
        EvidenceSourceType.SKIN_ASSESSMENT: skin,
    }

    results = await adapter.find(
        resident_id=resident_id,
        from_date=None,
        to_date=None,
        topics={"mobility"},
        statuses={"assessed"},
        current_only=False,
        limit=2,
    )

    assert [item.source_id for item in results] == [later.source_id, earlier.source_id]
    assert mobility.find_calls[0]["topics"] == {"mobility"}
    assert skin.find_calls[0]["statuses"] == {"assessed"}
    assert await adapter.get(
        resident_id=resident_id,
        source_type=EvidenceSourceType.SKIN_ASSESSMENT,
        source_id=later.source_id,
    ) == later
