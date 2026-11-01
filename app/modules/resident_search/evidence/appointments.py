import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import EvidenceDocument, EvidenceSourceType, AuthorityLevel

_SELECT = """
    SELECT f.id, f.resident_id, f.care_home_id, r.floor_id,
           f.appointment_type, f.scheduled_at, f.provider_name, f.location,
           f.reason, f.status, f.outcome, f.transport_required,
           f.escort_required, f.family_informed, f.notes,
           f.updated_at, f.deleted_at
    FROM APPOINTMENTS f
    JOIN residents r ON r.id = f.resident_id AND r.care_home_id = f.care_home_id
    WHERE f.resident_id = :resident_id
      AND f.deleted_at IS NULL AND r.deleted_at IS NULL AND r.floor_id IS NOT NULL
"""


class AppointmentsEvidenceAdapter:
    source_type = EvidenceSourceType.APPOINTMENT

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
                            AND f.scheduled_at >= COALESCE(CAST(:from_date AS TIMESTAMPTZ), '-infinity'::timestamptz)
                            AND f.scheduled_at < COALESCE(CAST(:to_date AS TIMESTAMPTZ), 'infinity'::timestamptz)
                            ORDER BY f.scheduled_at DESC, f.id DESC
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
        title = f"Appointment — {row['appointment_type'].replace('_', ' ')}"
        metadata = {
            key: row[key]
            for key in (
                "appointment_type",
                "scheduled_at",
                "provider_name",
                "reason",
                "outcome",
                "status",
                "location",
                "transport_required",
                "escort_required",
                "family_informed",
                "notes",
            )
        }
        parts = [title + "."]
        for label, key in (
            ("Location", "location"),
            ("Appointment type", "appointment_type"),
            ("Provider", "provider_name"),
            ("Reason", "reason"),
            ("Status", "status"),
            ("Outcome", "outcome"),
            ("Notes", "notes"),
        ):
            if row[key]:
                parts.append(f"{label}: {' '.join(str(row[key]).split())}")
        for label, key in (
            ("Transport required", "transport_required"),
            ("Escort required", "escort_required"),
            ("Family informed", "family_informed"),
        ):
            parts.append(f"{label}: {'Yes' if row[key] else 'No'}.")
        return EvidenceDocument(
            evidence_id=f"appointment:{row['id']}",
            source_type=EvidenceSourceType.APPOINTMENT,
            source_id=row["id"],
            resident_id=row["resident_id"],
            care_home_id=row["care_home_id"],
            floor_id=row["floor_id"],
            occurred_at=row["scheduled_at"],
            source_version=row["updated_at"],
            title=title,
            topic_tags={"appointment", "hospital"},  # only add hospital when applicable
            authority_level = AuthorityLevel.APPOINTMENT,
            status = row["status"],
            searchable_text=" ".join(parts),
            structured_metadata=metadata,
            time_precision="timestamp",
            effective_from=None,
            effective_to=None,
            is_deleted=row["deleted_at"] is not None,
            is_eligible=row["deleted_at"] is None,
        )
