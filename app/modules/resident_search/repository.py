import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.resident_search.models import (
    ResidentHistorySearch,
    ResidentHistorySearchCitation,
)
from app.modules.resident_search.schemas import (
    EvidenceCitation,
    SearchSourceType,
)

MAX_CITATIONS = 50
# Compatibility alias for existing callers. The cap is now applied to the
# complete multi-source result, not only fall evidence.
MAX_FALL_CITATIONS = MAX_CITATIONS


class ResidentSearchRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_resident_scope(
        self,
        resident_id: uuid.UUID,
    ) -> tuple[uuid.UUID, uuid.UUID | None] | None:
        row = (
            (
                await self._session.execute(
                    text("""
                     SELECT care_home_id, floor_id
                     FROM residents
                     WHERE id = :resident_id
                       AND deleted_at IS NULL
                     """),
                    {"resident_id": resident_id},
                )
            )
            .mappings()
            .one_or_none()
        )

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
                time_precision=citation.time_precision,
                source_date=citation.source_date,
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
            .options(selectinload(ResidentHistorySearch.citations))
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
                ResidentHistorySearchCitation.search_id == ResidentHistorySearch.id,
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
