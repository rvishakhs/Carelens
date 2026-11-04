import uuid
from datetime import datetime
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import EvidenceDocument, EvidenceSourceType, AuthorityLevel

_SELECT = """
    SELECT
        s.id,
        s.resident_id,
        s.care_home_id,
        r.floor_id,
        s.assessment_tool,
        s.total_score,
        s.risk_level,
        s.pressure_areas_checked,
        s.equipment_in_use,
        s.reposition_frequency,
        s.assessed_at,
        s.next_review_due,
        s.created_at,
        s.deleted_at
    FROM skin_integrity_assessments s
    JOIN residents r
      ON r.id = s.resident_id
     AND r.care_home_id = s.care_home_id
    WHERE s.resident_id = :resident_id
      AND s.deleted_at IS NULL
      AND r.deleted_at IS NULL
      AND r.floor_id IS NOT NULL
"""

class SkinAssessmentReader:
    def __init__(self, session: AsyncSession):
        self._session = session

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

        if from_date is not None and to_date is not None and from_date >= to_date:
            raise ValueError("from_date must be earlier than to_date")

        # Every record returned by this reader is mobility evidence.
        supported_topics = {
            "skin",
            "pressure_area",
            "repositioning",
            "wound",
            "tissue_viability",
        }

        if topics and not topics.intersection(supported_topics):
            return []

        # Assessment records are historical assessments, not active/completed events.
        if statuses and "assessed" not in statuses:
            return []

        query = text(
            _SELECT
            + """
                      AND s.assessed_at >= COALESCE(
                            CAST(:from_date AS TIMESTAMPTZ),
                            '-infinity'::timestamptz
                          )
                      AND s.assessed_at < COALESCE(
                            CAST(:to_date AS TIMESTAMPTZ),
                            'infinity'::timestamptz
                          )
                    ORDER BY s.assessed_at DESC, s.id DESC
                    LIMIT :limit
                    """
        )

        rows = (
            await self._session.execute(
                query,
                {
                    "resident_id": resident_id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "limit": limit,
                },
            )
        ).mappings().all()

        documents = [self._document(row) for row in rows]

        # This table has no active/effective-period fields. “Current” means
        # “most recently assessed” only; it does not mean a current care-plan rule.
        if current_only:
            return documents[:1]

        return documents

    async def get(
        self,
        *,
        resident_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> EvidenceDocument | None:
        row = (
            await self._session.execute(
                text(_SELECT + " AND s.id = :source_id"),
                {
                    "resident_id": resident_id,
                    "source_id": source_id,
                },
            )
        ).mappings().one_or_none()

        return self._document(row) if row is not None else None

    @staticmethod
    def _document(row: Mapping[str, Any]) -> EvidenceDocument:
        risk_level = row["risk_level"]
        total_score = row["total_score"]
        equipment_in_use = row["equipment_in_use"]
        reposition_frequency = row["reposition_frequency"]
        pressure_areas_checked = row["pressure_areas_checked"]

        title = "Skin assessment"

        parts = [title + "." + f"{row['assessment_tool']} skin-integrity assessment."]

        if pressure_areas_checked:
            parts.append(
                f"Pressure area in moniter: {str(pressure_areas_checked).replace('_', ' ')}."
            )

        if total_score:
            parts.append(f"Total score: {row['total_score']}.")

        if risk_level:
            parts.append(
                f"skin risk level: {str(risk_level).replace('_', ' ')}."
            )

        if equipment_in_use:
            parts.append(f"Equipment using is : {equipment_in_use}.")

        if reposition_frequency:
            parts.append(f"Regular reposition at: {', '.join(reposition_frequency)}.")

        metadata = {
            "assessment_tool": row["assessment_tool"],
            "total_score": row["total_score"],
            "risk_level": row["risk_level"],
            "pressure_areas_checked": pressure_areas_checked,
            "equipment_in_use": row["equipment_in_use"],
            "reposition_frequency": row["reposition_frequency"],
            "next_review_due": row["next_review_due"],
        },

        return EvidenceDocument(
            evidence_id=f"skin_assessment:{row['id']}",
            source_type=EvidenceSourceType.SKIN_ASSESSMENT,
            source_id=row["id"],

            resident_id=row["resident_id"],
            care_home_id=row["care_home_id"],
            floor_id=row["floor_id"],

            authority_level=AuthorityLevel.FORMAL_ASSESSMENT,
            topic_tags={
                "skin",
                "pressure_area",
                "repositioning",
                "wound",
                "tissue_viability",
            },
            status="assessed",

            occurred_at=row["assessed_at"],
            time_precision="timestamp",
            effective_from=None,
            effective_to=None,

            # See source-version note below.
            source_version=row["created_at"],

            title=title,
            searchable_text=" ".join(parts),
            structured_metadata=metadata,

            is_deleted=row["deleted_at"] is not None,
            is_eligible=row["deleted_at"] is None,
        )




