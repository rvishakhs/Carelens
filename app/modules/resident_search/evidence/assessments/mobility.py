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
        m.id,
        m.resident_id,
        m.care_home_id,
        r.floor_id,
        m.mobility_level,
        m.aids_used,
        m.transfer_method,
        m.falls_risk_score,
        m.falls_risk_level, 
        m.assessed_at,
        m.next_review_due,
        m.notes,
        m.created_at,
        m.deleted_at
    FROM mobility_assessments m
    JOIN residents r
      ON r.id = m.resident_id
     AND r.care_home_id = m.care_home_id
    WHERE m.resident_id = :resident_id
      AND m.deleted_at IS NULL
      AND r.deleted_at IS NULL
      AND r.floor_id IS NOT NULL
"""

class MobilityAssessmentReader:
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
        supported_topics = {"mobility", "transfer", "falls_risk", "aids"}
        if topics and not topics.intersection(supported_topics):
            return []

        # Assessment records are historical assessments, not active/completed events.
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
        mobility_level = row["mobility_level"]
        transfer_method = row["transfer_method"]
        aids_used = row["aids_used"] or []
        falls_risk_level = row["falls_risk_level"]

        title = "Mobility assessment"

        parts = [title + "."]

        if mobility_level:
            parts.append(
                f"Mobility level: {str(mobility_level).replace('_', ' ')}."
            )

        if transfer_method:
            parts.append(f"Transfer method: {transfer_method}.")

        if aids_used:
            parts.append(f"Aids used: {', '.join(aids_used)}.")

        if falls_risk_level:
            parts.append(
                f"Falls risk level: {str(falls_risk_level).replace('_', ' ')}."
            )

        metadata = {
            "mobility_level": mobility_level,
            "aids_used": aids_used,
            "transfer_method": transfer_method,
            "falls_risk_score": row["falls_risk_score"],
            "falls_risk_level": falls_risk_level,
            "next_review_due": row["next_review_due"],
            # Keep notes separate from searchable/model text for now.
            "has_notes": bool(row["notes"]),
        }

        return EvidenceDocument(
            evidence_id=f"mobility_assessment:{row['id']}",
            source_type=EvidenceSourceType.MOBILITY_ASSESSMENT,
            source_id=row["id"],

            resident_id=row["resident_id"],
            care_home_id=row["care_home_id"],
            floor_id=row["floor_id"],

            authority_level=AuthorityLevel.FORMAL_ASSESSMENT,
            topic_tags={"mobility", "transfer", "falls_risk", "aids"},
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




