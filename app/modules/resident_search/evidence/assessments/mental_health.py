
import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceDocument, EvidenceSourceType

_SELECT = """
    SELECT
        m.id,
        m.resident_id,
        m.care_home_id,
        r.floor_id,
        m.assessment_tool,
        m.total_score,
        m.interpretation,
        m.assessed_at,
        m.next_review_due,
        m.created_at,
        m.deleted_at
    FROM mental_health_assessments m
    JOIN residents r
      ON r.id = m.resident_id
     AND r.care_home_id = m.care_home_id
    WHERE m.resident_id = :resident_id
      AND m.deleted_at IS NULL
      AND r.deleted_at IS NULL
      AND r.floor_id IS NOT NULL
"""

class MentalHealthAssessmentReader:
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

        supported_topics = {
            "wellbeing",
            "behaviour",
            "mental_health",
            "distress",
        }
        if topics and not topics.intersection(supported_topics):
            return []

        if statuses and "assessed" not in statuses:
            return []

        query = text(
            _SELECT
            + """
                      AND m.assessed_at >= COALESCE(
                            CAST(:from_date AS TIMESTAMPTZ),
                            '-infinity'::timestamptz
                          )
                      AND m.assessed_at < COALESCE(
                            CAST(:to_date AS TIMESTAMPTZ),
                            'infinity'::timestamptz
                          )
                    ORDER BY m.assessed_at DESC, m.id DESC
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
                text(_SELECT + " AND m.id = :source_id"),
                {
                    "resident_id": resident_id,
                    "source_id": source_id,
                },
            )
        ).mappings().one_or_none()

        return self._document(row) if row is not None else None

    @staticmethod
    def _document(row: Mapping[str, Any]) -> EvidenceDocument:
        interpretation = row["interpretation"]
        total_score = row["total_score"]


        title = "Mental health assessment"
        parts = [
            f"{row['assessment_tool']} mental-health assessment."
        ]

        if total_score is not None:
            parts.append(f"Total score: {total_score}.")

        if interpretation:
            parts.append(
                f"Recorded interpretation: {' '.join(str(interpretation).split())}."
            )


        metadata = {
            "assessment_tool": row["assessment_tool"],
            "total_score": total_score,
            "interpretation": interpretation,
            "assessed_at": row["assessed_at"],
            "next_review_due": row["next_review_due"],
        }

        return EvidenceDocument(
            evidence_id=f"mental_health_assessment:{row['id']}",
            source_type=EvidenceSourceType.MENTAL_HEALTH_ASSESSMENT,
            source_id=row["id"],

            resident_id=row["resident_id"],
            care_home_id=row["care_home_id"],
            floor_id=row["floor_id"],

            authority_level=AuthorityLevel.FORMAL_ASSESSMENT,
            topic_tags={
                 "wellbeing",
                "behaviour",
                "mental_health",
                "distress",
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
            is_implausible=False
        )
