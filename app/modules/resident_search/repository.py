import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.schemas import (
    EvidenceCitation,
    SearchSourceType,
)


class ResidentSearchRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def resident_exists(self, resident_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            text("""
                SELECT 1
                FROM residents
                WHERE id = :resident_id
                  AND deleted_at IS NULL
            """),
            {"resident_id": resident_id},
        )
        return result.scalar_one_or_none() is not None

    async def find_falls(
        self,
        resident_id: uuid.UUID,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> list[EvidenceCitation]:
        rows = (
            await self._session.execute(
                text("""
                    SELECT
                        id,
                        occurred_at,
                        severity,
                        location,
                        injuries,
                        likely_cause,
                        action_taken
                    FROM falls_incidents
                    WHERE resident_id = :resident_id
                      AND deleted_at IS NULL
                      AND (:from_date IS NULL OR occurred_at >= :from_date)
                      AND (:to_date IS NULL OR occurred_at < :to_date)
                    ORDER BY occurred_at DESC
                    LIMIT 50
                """),
                {
                    "resident_id": resident_id,
                    "from_date": from_date,
                    "to_date": to_date,
                },
            )
        ).mappings().all()

        return [
            EvidenceCitation(
                evidence_id=f"fall:{row['id']}",
                source_type=SearchSourceType.FALL,
                source_id=row["id"],
                occurred_at=row["occurred_at"],
                title=f"Fall — {row['severity']}",
                excerpt=" ".join(
                    part
                    for part in [
                        f"Location: {row['location']}." if row["location"] else None,
                        f"Injuries: {row['injuries']}." if row["injuries"] else None,
                        f"Likely cause: {row['likely_cause']}." if row["likely_cause"] else None,
                        f"Action taken: {row['action_taken']}." if row["action_taken"] else None,
                    ]
                    if part
                ) or None,
            )
            for row in rows
        ]