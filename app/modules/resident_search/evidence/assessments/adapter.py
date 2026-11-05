import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.assessments.mental_health import MentalHealthAssessmentReader
from app.modules.resident_search.evidence.assessments.mobility import MobilityAssessmentReader
from app.modules.resident_search.evidence.assessments.nutrition import NutritionAssessmentReader
from app.modules.resident_search.evidence.assessments.skin import SkinAssessmentReader
from app.modules.resident_search.evidence.models import EvidenceDocument, EvidenceSourceType


class AssessmentEvidenceAdapter:
    source_type = EvidenceSourceType.ASSESSMENT

    def __init__(self, session: AsyncSession):
        self._readers = {
            EvidenceSourceType.MOBILITY_ASSESSMENT:
                MobilityAssessmentReader(session),

            EvidenceSourceType.NUTRITION_ASSESSMENT:
                NutritionAssessmentReader(session),

            EvidenceSourceType.SKIN_ASSESSMENT:
                SkinAssessmentReader(session),

            EvidenceSourceType.MENTAL_HEALTH_ASSESSMENT:
                MentalHealthAssessmentReader(session),
        }
    async def find(
            self,
            *,
            resident_id: uuid.UUID,
            from_date: datetime | None,
            to_date: datetime | None,
            topics: set[str] | None = None,
            statuses: set[str] | None = None,
            current_only: bool = False,
            limit: int,
    ) -> list[EvidenceDocument]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        documents: list[EvidenceDocument] = []

        for reader in self._readers.values():
            documents.extend(
                await reader.find(
                    resident_id=resident_id,
                    from_date=from_date,
                    to_date=to_date,
                    topics=topics,
                    statuses=statuses,
                    current_only=current_only,
                    limit=limit,
                )
            )

        return sorted(
            documents,
            key=lambda item: (
                item.occurred_at is not None,
                item.occurred_at,
                str(item.source_id),
            ),
            reverse=True,
        )[:limit]

    async def get(
        self,
        *,
        resident_id: uuid.UUID,
        source_type: EvidenceSourceType,
        source_id: uuid.UUID,
    ) -> EvidenceDocument | None:
        reader = self._readers.get(source_type)

        if reader is None:
            return None

        return await reader.get(
            resident_id=resident_id,
            source_id=source_id,
        )