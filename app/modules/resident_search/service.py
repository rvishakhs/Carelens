import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from app import EventBus, NotFoundError, ResidentHistorySearched, ValidationError
from app.modules.resident_search.evidence.models import EvidenceDocument, EvidenceSourceType
from app.modules.resident_search.evidence.ports import EvidenceSourceAdapter
from app.modules.resident_search.repository import MAX_CITATIONS, ResidentSearchRepository
from app.modules.resident_search.schemas import (
    AnswerStatus,
    EvidenceCitation,
    ResidentSearchRequest,
    ResidentSearchResponse,
    ResidentSearchSourceResponse,
    SearchMode,
)

_SUPPORTED_SOURCE_TYPES = frozenset({EvidenceSourceType.FALL, EvidenceSourceType.APPOINTMENT})
_SOURCE_QUERY_TERMS: dict[EvidenceSourceType, frozenset[str]] = {
    EvidenceSourceType.FALL: frozenset({"fall", "falls", "fell", "slip", "slipped", "trip", "tripped"}),
    EvidenceSourceType.APPOINTMENT: frozenset({"appointment", "appointments", "hospital", "clinic", "consultation", "gp"}),
}
_SOURCE_LABELS = {EvidenceSourceType.FALL: "fall", EvidenceSourceType.APPOINTMENT: "appointment"}


class ResidentSearchService:
    def __init__(self, repository: ResidentSearchRepository, event_bus: EventBus, adapters: Mapping[EvidenceSourceType, EvidenceSourceAdapter]):
        self._repository = repository
        self._event_bus = event_bus
        self._adapters = dict(adapters)

    def _adapter_for(self, source_type: EvidenceSourceType) -> EvidenceSourceAdapter:
        try:
            return self._adapters[source_type]
        except KeyError as exc:
            raise ValidationError(f"{source_type.value} search is not available") from exc

    async def search(self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, resident_id: uuid.UUID, payload: ResidentSearchRequest) -> ResidentSearchResponse:
        if payload.mode != SearchMode.EVIDENCE:
            raise ValidationError("AI answer mode is not available yet")
        source_types = self._requested_source_types(payload)
        scope = await self._repository.get_resident_scope(resident_id)
        if scope is None:
            raise NotFoundError(f"resident {resident_id} not found")
        resident_care_home_id, floor_id = scope
        if resident_care_home_id != care_home_id or floor_id is None:
            raise NotFoundError(f"resident {resident_id} not found")

        documents: list[EvidenceDocument] = []
        for source_type in source_types:
            source_documents = await self._adapter_for(source_type).find(
                resident_id=resident_id, from_date=payload.from_date, to_date=payload.to_date, limit=MAX_CITATIONS + 1
            )
            documents.extend(document for document in source_documents if self._usable(document, resident_id, care_home_id, source_type))

        citations = [
            EvidenceCitation(
                evidence_id=document.evidence_id, source_type=document.source_type, source_id=document.source_id,
                source_version=document.source_version, occurred_at=document.occurred_at, title=document.title,
                excerpt=document.searchable_text,
            )
            for document in documents
        ]
        citations.sort(key=lambda citation: citation.occurred_at, reverse=True)
        results_were_truncated = len(citations) > MAX_CITATIONS
        citations = citations[:MAX_CITATIONS]
        period = "the selected period" if payload.from_date or payload.to_date else "available record history"
        source_label = self._source_label(source_types)
        if not citations:
            answer, answer_status = f"No {source_label} records were found in {period}.", AnswerStatus.NO_EVIDENCE
        elif results_were_truncated:
            answer, answer_status = f"At least {MAX_CITATIONS} {source_label} records were found in {period}.", AnswerStatus.PARTIAL
        else:
            answer, answer_status = self._answer_for(citations, period), AnswerStatus.SUPPORTED

        limitations = [
            f"This result searches approved {source_label} records only.",
            "Matches in care events, observations and notes are not included yet.",
            "Verify details against the cited source records.",
        ]
        if results_were_truncated:
            limitations.append(f"Only the {MAX_CITATIONS} most recent records are shown.")
        search = await self._repository.create_search(
            care_home_id=resident_care_home_id, floor_id=floor_id, resident_id=resident_id, requested_by=actor_user_id,
            mode=SearchMode.EVIDENCE.value, answer=answer, answer_status=answer_status.value,
            coverage_limitations=limitations, expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        await self._repository.add_citations(search=search, citations=citations)
        await self._event_bus.publish(ResidentHistorySearched(
            care_home_id=care_home_id, actor_user_id=actor_user_id, resident_id=resident_id, result_count=len(citations)
        ))
        return ResidentSearchResponse(
            search_id=search.id, resident_id=resident_id, answer=answer, answer_status=answer_status,
            coverage_limitations=limitations, citations=citations,
        )

    async def get_saved_search(self, resident_id: uuid.UUID, search_id: uuid.UUID) -> ResidentSearchResponse:
        search = await self._repository.get_search(search_id=search_id, resident_id=resident_id)
        if search is None:
            raise NotFoundError(f"history search {search_id} not found")
        citations = [
            EvidenceCitation(
                evidence_id=f"{citation.source_type}:{citation.source_id}", source_type=EvidenceSourceType(citation.source_type),
                source_id=citation.source_id, source_version=citation.source_version, occurred_at=citation.occurred_at,
                title=citation.title, excerpt=citation.excerpt,
            )
            for citation in sorted(search.citations, key=lambda item: item.rank)
        ]
        return ResidentSearchResponse(
            search_id=search.id, resident_id=search.resident_id, answer=search.answer,
            answer_status=AnswerStatus(search.answer_status), coverage_limitations=search.coverage_limitations, citations=citations,
        )

    async def get_source(self, resident_id: uuid.UUID, search_id: uuid.UUID, source_type: EvidenceSourceType, source_id: uuid.UUID) -> ResidentSearchSourceResponse:
        citation = await self._repository.get_citation(
            search_id=search_id, resident_id=resident_id, source_type=source_type, source_id=source_id
        )
        if citation is None:
            raise NotFoundError(f"history search source {source_id} not found")
        source = await self._adapter_for(source_type).get(source_id=source_id, resident_id=resident_id)
        scope = await self._repository.get_resident_scope(resident_id)
        if scope is None or source is None or not self._usable(source, resident_id, scope[0], source_type):
            raise NotFoundError(f"history search source {source_id} not found")
        return ResidentSearchSourceResponse(
            source_type=source_type, source_id=source.source_id, occurred_at=source.occurred_at,
            source_version=source.source_version, title=source.title, details=source.structured_metadata,
            changed_since_search=source.source_version != citation.source_version,
        )

    @staticmethod
    def _requested_source_types(payload: ResidentSearchRequest) -> set[EvidenceSourceType]:
        requested = set(payload.source_types or [])
        unsupported = requested - _SUPPORTED_SOURCE_TYPES
        if unsupported:
            names = ", ".join(sorted(source_type.value for source_type in unsupported))
            raise ValidationError(f"Source types not available for deterministic search: {names}.")
        if requested:
            return requested
        words = set(re.findall(r"[a-z]+", payload.question.casefold()))
        inferred = {source_type for source_type, terms in _SOURCE_QUERY_TERMS.items() if words.intersection(terms)}
        return inferred or _SUPPORTED_SOURCE_TYPES

    @staticmethod
    def _source_label(source_types: set[EvidenceSourceType]) -> str:
        return " and ".join(_SOURCE_LABELS[source_type] for source_type in sorted(source_types, key=lambda value: value.value))

    @staticmethod
    def _answer_for(citations: list[EvidenceCitation], period: str) -> str:
        counts: dict[EvidenceSourceType, int] = {}
        for citation in citations:
            counts[citation.source_type] = counts.get(citation.source_type, 0) + 1
        parts = []
        for source_type in sorted(counts, key=lambda value: value.value):
            count, noun = counts[source_type], _SOURCE_LABELS[source_type]
            parts.append(f"{count} {noun}{'' if count == 1 else 's'}")
        return f"{' and '.join(parts).capitalize()} {'was' if len(citations) == 1 else 'were'} found in {period}."

    @staticmethod
    def _usable(document: EvidenceDocument, resident_id: uuid.UUID, care_home_id: uuid.UUID, source_type: EvidenceSourceType) -> bool:
        return (
            document.resident_id == resident_id and document.care_home_id == care_home_id
            and document.source_type == source_type and not document.is_deleted and document.is_eligible
        )
