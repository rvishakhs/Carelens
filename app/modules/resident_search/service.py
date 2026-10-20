import re
import uuid
from datetime import UTC, datetime, timedelta

from app import EventBus, NotFoundError, ResidentHistorySearched, ValidationError
from app.modules.resident_search.repository import MAX_FALL_CITATIONS, ResidentSearchRepository
from app.modules.resident_search.schemas import (
    AnswerStatus,
    EvidenceCitation,
    ResidentSearchRequest,
    ResidentSearchResponse,
    ResidentSearchSourceResponse,
    SearchMode,
    SearchSourceType,
)


_SUPPORTED_SOURCE_TYPES = frozenset({SearchSourceType.FALL})
_FALL_QUERY_TERMS = frozenset({"fall", "falls", "fell", "slip", "slipped", "trip", "tripped"})


class ResidentSearchService:
    def __init__(self, repository: ResidentSearchRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus

    async def search(
        self,
        care_home_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        resident_id: uuid.UUID,
        payload: ResidentSearchRequest,
    ) -> ResidentSearchResponse:
        if payload.mode != SearchMode.EVIDENCE:
            raise ValidationError("AI answer mode is not available yet")

        self._requested_source_types(payload)

        scope = await self._repository.get_resident_scope(resident_id)
        if scope is None:
            raise NotFoundError(f"resident {resident_id} not found")

        resident_care_home_id, floor_id = scope
        if resident_care_home_id != care_home_id or floor_id is None:
            raise NotFoundError(f"resident {resident_id} not found")

        citations = await self._repository.find_falls(
            resident_id,
            payload.from_date,
            payload.to_date,
        )
        citations.sort(key=lambda citation: citation.occurred_at, reverse=True)

        results_were_truncated = len(citations) > MAX_FALL_CITATIONS
        citations = citations[:MAX_FALL_CITATIONS]
        period = "the selected period" if payload.from_date or payload.to_date else "available fall record history"

        if not citations:
            answer = f"No fall records were found in {period}."
            answer_status = AnswerStatus.NO_EVIDENCE
        elif results_were_truncated:
            answer = f"At least {MAX_FALL_CITATIONS} falls were recorded in {period}."
            answer_status = AnswerStatus.PARTIAL
        elif len(citations) == 1:
            answer = f"One fall was recorded in {period}."
            answer_status = AnswerStatus.SUPPORTED
        else:
            answer = f"{len(citations)} falls were recorded in {period}."
            answer_status = AnswerStatus.SUPPORTED

        limitations = [
            "This result currently searches approved fall records only.",
            "Verify details against the cited source records.",
        ]
        if results_were_truncated:
            limitations.append(f"Only the {MAX_FALL_CITATIONS} most recent fall records are shown.")

        search = await self._repository.create_search(
            care_home_id=resident_care_home_id,
            floor_id=floor_id,
            resident_id=resident_id,
            requested_by=actor_user_id,
            mode=SearchMode.EVIDENCE.value,
            answer=answer,
            answer_status=answer_status.value,
            coverage_limitations=limitations,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        await self._repository.add_citations(search=search, citations=citations)

        await self._event_bus.publish(
            ResidentHistorySearched(
                care_home_id=care_home_id,
                actor_user_id=actor_user_id,
                resident_id=resident_id,
                result_count=len(citations),
            )
        )
        return ResidentSearchResponse(
            search_id=search.id,
            resident_id=resident_id,
            answer=answer,
            answer_status=answer_status,
            coverage_limitations=limitations,
            citations=citations,
        )

    async def get_saved_search(
        self,
        resident_id: uuid.UUID,
        search_id: uuid.UUID,
    ) -> ResidentSearchResponse:
        search = await self._repository.get_search(search_id=search_id, resident_id=resident_id)
        if search is None:
            raise NotFoundError(f"history search {search_id} not found")

        citations = [
            EvidenceCitation(
                evidence_id=f"{citation.source_type}:{citation.source_id}",
                source_type=SearchSourceType(citation.source_type),
                source_id=citation.source_id,
                source_version=citation.source_version,
                occurred_at=citation.occurred_at,
                title=citation.title,
                excerpt=citation.excerpt,
            )
            for citation in sorted(search.citations, key=lambda item: item.rank)
        ]
        return ResidentSearchResponse(
            search_id=search.id,
            resident_id=search.resident_id,
            answer=search.answer,
            answer_status=AnswerStatus(search.answer_status),
            coverage_limitations=search.coverage_limitations,
            citations=citations,
        )

    async def get_source(
        self,
        resident_id: uuid.UUID,
        search_id: uuid.UUID,
        source_type: SearchSourceType,
        source_id: uuid.UUID,
    ) -> ResidentSearchSourceResponse:
        citation = await self._repository.get_citation(
            search_id=search_id,
            resident_id=resident_id,
            source_type=source_type,
            source_id=source_id,
        )
        if citation is None:
            raise NotFoundError(f"history search source {source_id} not found")

        source = await self._repository.get_current_source(
            source_type=source_type,
            source_id=source_id,
            resident_id=resident_id,
        )
        if source is None:
            raise NotFoundError(f"history search source {source_id} not found")

        return ResidentSearchSourceResponse(
            source_type=source_type,
            source_id=source["source_id"],
            occurred_at=source["occurred_at"],
            source_version=source["source_version"],
            title=source["title"],
            details=source["details"],
            changed_since_search=source["source_version"] != citation.source_version,
        )

    @staticmethod
    def _requested_source_types(payload: ResidentSearchRequest) -> set[SearchSourceType]:
        requested_source_types = set(payload.source_types or [])
        if not requested_source_types:
            question_words = set(re.findall(r"[a-z]+", payload.question.casefold()))
            if not question_words.intersection(_FALL_QUERY_TERMS):
                raise ValidationError(
                    "Only fall-history search is available currently. "
                    "Ask a fall-related question or set source_types to ['fall']."
                )
            return {SearchSourceType.FALL}

        unsupported_source_types = requested_source_types - _SUPPORTED_SOURCE_TYPES
        if unsupported_source_types:
            unsupported = ", ".join(sorted(source_type.value for source_type in unsupported_source_types))
            raise ValidationError(
                f"Source types not available for deterministic search: {unsupported}. "
                "Only fall is available currently."
            )

        return requested_source_types
