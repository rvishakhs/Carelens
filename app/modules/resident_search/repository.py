import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.models import (
    ResidentHistorySearch,
    ResidentHistorySearchCitation,
)
from app.modules.resident_search.schemas import (
    EvidenceCitation,
    SearchSourceType,
)


MAX_FALL_CITATIONS = 50


class ResidentSearchRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

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
                        updated_at,
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
                    ORDER BY occurred_at DESC, id DESC
                    -- Fetch one extra row so the service can say when the displayed
                    -- evidence was truncated, rather than implying a complete count.
                    LIMIT :limit
                """),
                {
                    "resident_id": resident_id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "limit": MAX_FALL_CITATIONS + 1,
                },
            )
        ).mappings().all()

        return [
            EvidenceCitation(
                evidence_id=f"fall:{row['id']}",
                source_type=SearchSourceType.FALL,
                source_id=row["id"],
                source_version=row["updated_at"],
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

    async def get_resident_scope(
        self,
        resident_id: uuid.UUID,
    ) -> tuple[uuid.UUID, uuid.UUID | None] | None:
        row = (
            await self._session.execute(
                text("""
                     SELECT care_home_id, floor_id
                     FROM residents
                     WHERE id = :resident_id
                       AND deleted_at IS NULL
                     """),
                {"resident_id": resident_id},
            )
        ).mappings().one_or_none()

        if row is None:
            return None

        return row["care_home_id"], row["floor_id"]

    async def create_search(
        self,
        *,
        care_home_id: uuid.UUID,
        floor_id: uuid.UUID,
        resident_id: uuid.UUID,
        requested_by: uuid.UUID,
        mode: str,
        answer: str,
        answer_status: str,
        coverage_limitations: list[str],
        expires_at: datetime,
    ) -> ResidentHistorySearch:
        search = ResidentHistorySearch(
            care_home_id=care_home_id,
            floor_id=floor_id,
            resident_id=resident_id,
            requested_by=requested_by,
            mode=mode,
            answer=answer,
            answer_status=answer_status,
            coverage_limitations=coverage_limitations,
            expires_at=expires_at,
        )

        self._session.add(search)
        await self._session.flush()

        return search

    async def add_citations(
        self,
        *,
        search: ResidentHistorySearch,
        citations: Sequence[EvidenceCitation],
    ) -> list[ResidentHistorySearchCitation]:
        rows = [
            ResidentHistorySearchCitation(
                search_id=search.id,
                care_home_id=search.care_home_id,
                floor_id=search.floor_id,
                resident_id=search.resident_id,
                source_type=citation.source_type.value,
                source_id=citation.source_id,
                source_version=citation.source_version,
                occurred_at=citation.occurred_at,
                title=citation.title,
                excerpt=citation.excerpt,
                rank=rank,
            )
            for rank, citation in enumerate(citations, start=1)
        ]

        self._session.add_all(rows)
        await self._session.flush()

        return rows

    async def get_search(
        self,
        *,
        search_id: uuid.UUID,
        resident_id: uuid.UUID,
    ) -> ResidentHistorySearch | None:
        statement = (
            select(ResidentHistorySearch)
            .where(
                ResidentHistorySearch.id == search_id,
                ResidentHistorySearch.resident_id == resident_id,
                ResidentHistorySearch.expires_at > func.now(),
            )
            .options(
                selectinload(ResidentHistorySearch.citations)
            )
        )

        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_citation(
        self,
        *,
        search_id: uuid.UUID,
        resident_id: uuid.UUID,
        source_type: SearchSourceType,
        source_id: uuid.UUID,
    ) -> ResidentHistorySearchCitation | None:
        statement = (
            select(ResidentHistorySearchCitation)
            .join(
                ResidentHistorySearch,
                ResidentHistorySearchCitation.search_id
                == ResidentHistorySearch.id,
            )
            .where(
                ResidentHistorySearchCitation.search_id == search_id,
                ResidentHistorySearchCitation.resident_id == resident_id,
                ResidentHistorySearchCitation.source_type == source_type.value,
                ResidentHistorySearchCitation.source_id == source_id,
                ResidentHistorySearch.expires_at > func.now(),
            )
        )

        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_current_source(
        self,
        *,
        source_type: SearchSourceType,
        source_id: uuid.UUID,
        resident_id: uuid.UUID,
    ) -> dict[str, object] | None:
        if source_type == SearchSourceType.FALL:
            row = (
                await self._session.execute(
                    text("""
                        SELECT
                            id,
                            occurred_at,
                            updated_at,
                            severity,
                            location,
                            witnessed,
                            injuries,
                            likely_cause,
                            action_taken,
                            post_fall_observations_required
                        FROM falls_incidents
                        WHERE id = :source_id
                          AND resident_id = :resident_id
                          AND deleted_at IS NULL
                    """),
                    {
                        "source_id": source_id,
                        "resident_id": resident_id,
                    },
                )
            ).mappings().one_or_none()

            if row is None:
                return None

            return {
                "source_type": "fall",
                "source_id": row["id"],
                "occurred_at": row["occurred_at"],
                "source_version": row["updated_at"],
                "title": f"Fall — {row['severity']}",
                "details": {
                    "location": row["location"],
                    "witnessed": row["witnessed"],
                    "injuries": row["injuries"],
                    "likely_cause": row["likely_cause"],
                    "action_taken": row["action_taken"],
                    "post_fall_observations_required": row[
                        "post_fall_observations_required"
                    ],
                },
            }

        return None
