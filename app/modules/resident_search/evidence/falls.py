"""Fall evidence from authoritative records, using the caller's RLS session.

Text is an allowlisted local display/search projection, not anonymised model input.
No names, identifiers or staff fields are added to the projection. Clinical free
text can still contain personal data and must pass gateway controls before egress.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import EvidenceDocument, EvidenceSourceType, AuthorityLevel

_SELECT = """
    SELECT f.id, f.resident_id, f.care_home_id, r.floor_id,
           f.occurred_at, f.updated_at, f.deleted_at, f.severity,
           f.location, f.witnessed, f.injuries, f.likely_cause, f.action_taken,
           f.post_fall_observations_required, f.family_informed
    FROM falls_incidents f
    JOIN residents r ON r.id = f.resident_id AND r.care_home_id = f.care_home_id
    WHERE f.resident_id = :resident_id
      AND f.deleted_at IS NULL AND r.deleted_at IS NULL AND r.floor_id IS NOT NULL
"""


class FallsEvidenceAdapter:
    source_type = EvidenceSourceType.FALL

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
        rows = (
            (
                await self._session.execute(
                    text(
                        _SELECT
                        + """
                AND f.occurred_at >= COALESCE(CAST(:from_date AS TIMESTAMPTZ), '-infinity'::timestamptz)
                AND f.occurred_at < COALESCE(CAST(:to_date AS TIMESTAMPTZ), 'infinity'::timestamptz)
                ORDER BY f.occurred_at DESC, f.id DESC
                LIMIT :limit
            """
                    ),
                    {"resident_id": resident_id, "from_date": from_date, "to_date": to_date, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return [self._document(row) for row in rows]

    async def get(self, *, resident_id: uuid.UUID, source_id: uuid.UUID) -> EvidenceDocument | None:
        row = (
            (
                await self._session.execute(
                    text(_SELECT + " AND f.id = :source_id"),
                    {"resident_id": resident_id, "source_id": source_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return self._document(row) if row is not None else None

    @staticmethod
    def _document(row: Mapping[str, Any]) -> EvidenceDocument:
        title = f"Fall — {row['severity'].replace('_', ' ')}"
        metadata = {
            key: row[key]
            for key in (
                "severity",
                "location",
                "witnessed",
                "injuries",
                "likely_cause",
                "action_taken",
                "post_fall_observations_required",
                "family_informed",
            )
        }
        parts = [title + "."]
        for label, key in (
            ("Location", "location"),
            ("Injuries", "injuries"),
            ("Likely cause", "likely_cause"),
            ("Action taken", "action_taken"),
        ):
            if row[key]:
                parts.append(f"{label}: {' '.join(str(row[key]).split())}")
        for label, key in (
            ("Witnessed", "witnessed"),
            ("Post-fall observations required", "post_fall_observations_required"),
            ("Family informed", "family_informed"),
        ):
            parts.append(f"{label}: {'Yes' if row[key] else 'No'}.")
        return EvidenceDocument(
            evidence_id=f"fall:{row['id']}",
            source_type=EvidenceSourceType.FALL,
            source_id=row["id"],
            topic_tags={"fall", "mobility", "safety"},
            authority_level = AuthorityLevel.STRUCTURED_INCIDENT,
            status = "recorded",
            source_version = row["updated_at"],
            resident_id=row["resident_id"],
            care_home_id=row["care_home_id"],
            floor_id=row["floor_id"],
            occurred_at=row["occurred_at"],
            title=title,
            searchable_text=" ".join(parts),
            structured_metadata=metadata,
            time_precision="timestamp",
            effective_from=None,
            effective_to=None,
            is_deleted=row["deleted_at"] is not None,
            is_eligible=row["deleted_at"] is None,
            is_implausible=True
        )
