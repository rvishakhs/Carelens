from app.modules.resident_search.evidence.assessments.mental_health import MentalHealthAssessmentReader
from app.modules.resident_search.evidence.assessments.mobility import MobilityAssessmentReader
from app.modules.resident_search.evidence.assessments.nutrition import NutritionAssessmentReader
from app.modules.resident_search.evidence.assessments.skin import SkinAssessmentReader
from app.modules.resident_search.evidence.models import EvidenceSourceType
from sqlalchemy.ext.asyncio import AsyncSession








class AssessmentEvidenceAdapter:
    source_type = EvidenceSourceType.SOURCE_GROUP

    def __init__(self, session: AsyncSession):
        self._mobility = MobilityAssessmentReader(session)
        self._nutrition = NutritionAssessmentReader(session)
        self._skin = SkinAssessmentReader(session)
        self._mental_health = MentalHealthAssessmentReader(session)

    async def find(self, *, resident_id, from_date, to_date, limit):
        documents = [
            *await self._mobility.find(self, resident_id, from_date, to_date),
            *await self._nutrition.find(self, resident_id, from_date, to_date),
            *await self._skin.find(...),
            *await self._mental_health.find(...),
        ]
        return sorted(
            documents,
            key=lambda item: item.occurred_at,
            reverse=True,
        )[:limit]

    async def get(self, *, resident_id, source_id):
        # Usually needs source_type too, because IDs come from different tables.
        ...