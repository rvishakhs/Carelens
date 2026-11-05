import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app import InMemoryEventBus, NotFoundError, ValidationError
from app.modules.resident_search.events import ResidentHistorySearched
from app.modules.resident_search.evidence.careplan import CarePlanEvidenceAdapter
from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceDocument, EvidenceSourceType
from app.modules.resident_search.evidence.revisions import revision_token
from app.modules.resident_search.repository import MAX_FALL_CITATIONS
from app.modules.resident_search.schemas import (
    AnswerStatus,
    EvidenceCitation,
    ResidentSearchRequest,
    SearchMode,
    SearchSourceType,
)
from app.modules.resident_search.service import ResidentSearchService
from tests.unit.resident_search.test_careplan_adapter import plan_row


def fall_adapters(adapter: object) -> dict[EvidenceSourceType, object]:
    return {EvidenceSourceType.FALL: adapter}


def fall_citation(
    *,
    source_id: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
) -> EvidenceCitation:
    source_id = source_id or uuid.uuid4()
    occurred_at = occurred_at or datetime(2026, 10, 1, 10, tzinfo=UTC)
    return EvidenceCitation(
        evidence_id=f"fall:{source_id}",
        source_type=SearchSourceType.FALL,
        source_id=source_id,
        source_version=occurred_at,
        occurred_at=occurred_at,
        title="Fall — no injury",
        excerpt="Location: lounge.",
    )


class StubSearchRepository:
    source_type = EvidenceSourceType.FALL

    def __init__(
        self,
        citations: list[EvidenceCitation] | None = None,
        *,
        scope: tuple[uuid.UUID, uuid.UUID | None] | None = None,
    ):
        self.citations = citations or []
        self.scope = scope
        self.search_id = uuid.uuid4()
        self.create_search_kwargs: dict[str, object] | None = None
        self.added_citations: list[EvidenceCitation] | None = None
        self.persisted_search = None
        self.persisted_citation = None
        self.current_source: dict[str, object] | None = None

    async def get_resident_scope(self, resident_id: uuid.UUID):
        return self.scope

    async def find(self, *, resident_id, from_date, to_date, limit):
        return [
            EvidenceDocument(
                **citation.model_dump(exclude={"excerpt"}),
                resident_id=resident_id,
                care_home_id=self.scope[0],
                floor_id=self.scope[1],
                searchable_text=citation.excerpt or "",
                structured_metadata={},
                topic_tags={"fall"},
                authority_level=AuthorityLevel.STRUCTURED_INCIDENT,
                status=None,
                time_precision="timestamp",
                effective_from=None,
                effective_to=None,
                is_deleted=False,
                is_eligible=True,
            )
            for citation in self.citations
        ]

    async def get(self, *, resident_id, source_id):
        if self.current_source is None:
            return None
        return EvidenceDocument(
            evidence_id=f"fall:{source_id}",
            source_type=EvidenceSourceType.FALL,
            source_id=source_id,
            resident_id=resident_id,
            care_home_id=self.scope[0],
            floor_id=self.scope[1],
            occurred_at=self.current_source["occurred_at"],
            source_version=self.current_source["source_version"],
            title=self.current_source["title"],
            searchable_text="",
            structured_metadata=self.current_source["details"],
            topic_tags={"fall"},
            authority_level=AuthorityLevel.STRUCTURED_INCIDENT,
            status=None,
            time_precision="timestamp",
            effective_from=None,
            effective_to=None,
            is_deleted=False,
            is_eligible=True,
        )

    async def create_search(self, **kwargs):
        self.create_search_kwargs = kwargs
        return SimpleNamespace(id=self.search_id)

    async def add_citations(self, *, search, citations):
        self.added_citations = list(citations)
        return []

    async def get_search(self, *, search_id, resident_id):
        return self.persisted_search

    async def get_citation(self, *, search_id, resident_id, source_type, source_id):
        return self.persisted_citation

    async def get_current_source(self, *, source_type, source_id, resident_id):
        return self.current_source


async def test_search_persists_citations_and_publishes_metadata_only_audit_event():
    resident_id = uuid.uuid4()
    care_home_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = StubSearchRepository([fall_citation()], scope=(care_home_id, uuid.uuid4()))
    event_bus = InMemoryEventBus()
    events: list[ResidentHistorySearched] = []

    async def capture(event: ResidentHistorySearched) -> None:
        events.append(event)

    event_bus.subscribe(ResidentHistorySearched, capture)
    response = await ResidentSearchService(repository, event_bus, fall_adapters(repository)).search(
        care_home_id,
        actor_id,
        resident_id,
        ResidentSearchRequest(question="Show the resident's fall history"),
    )

    assert response.search_id == repository.search_id
    assert response.answer == "1 fall was found in available record history."
    assert response.answer_status == AnswerStatus.SUPPORTED
    assert response.citations == repository.citations
    assert repository.create_search_kwargs is not None
    assert repository.create_search_kwargs["care_home_id"] == care_home_id
    assert repository.create_search_kwargs["resident_id"] == resident_id
    assert repository.create_search_kwargs["requested_by"] == actor_id
    assert repository.create_search_kwargs["mode"] == SearchMode.EVIDENCE.value
    assert repository.create_search_kwargs["answer_status"] == AnswerStatus.SUPPORTED.value
    assert repository.added_citations == repository.citations

    assert len(events) == 1
    event = events[0]
    assert event.care_home_id == care_home_id
    assert event.actor_user_id == actor_id
    assert event.resident_id == resident_id
    assert event.result_count == 1
    # Audit events deliberately carry metadata only, never the staff question or
    # clinical excerpts that would create a second sensitive copy of the record.
    assert "question" not in event.model_dump()
    assert "excerpt" not in event.model_dump()


async def test_search_returns_no_evidence_when_no_fall_records_match():
    care_home_id = uuid.uuid4()
    repository = StubSearchRepository(scope=(care_home_id, uuid.uuid4()))
    response = await ResidentSearchService(repository, InMemoryEventBus(), fall_adapters(repository)).search(
        care_home_id,
        uuid.uuid4(),
        uuid.uuid4(),
        ResidentSearchRequest(
            question="What falls were recorded?",
            from_date=datetime(2026, 9, 1, tzinfo=UTC),
            to_date=datetime(2026, 10, 1, tzinfo=UTC),
            source_types=[SearchSourceType.FALL],
        ),
    )

    assert response.answer == "No fall records were found in the selected period."
    assert response.answer_status == AnswerStatus.NO_EVIDENCE
    assert response.citations == []
    assert repository.added_citations == []


async def test_search_marks_capped_results_as_partial():
    care_home_id = uuid.uuid4()
    citations = [
        fall_citation(occurred_at=datetime(2026, 10, 1, tzinfo=UTC) - timedelta(minutes=index))
        for index in range(MAX_FALL_CITATIONS + 1)
    ]
    repository = StubSearchRepository(citations, scope=(care_home_id, uuid.uuid4()))

    response = await ResidentSearchService(repository, InMemoryEventBus(), fall_adapters(repository)).search(
        care_home_id,
        uuid.uuid4(),
        uuid.uuid4(),
        ResidentSearchRequest(question="Show fall history", source_types=[SearchSourceType.FALL]),
    )

    assert response.answer_status == AnswerStatus.PARTIAL
    assert response.answer == f"At least {MAX_FALL_CITATIONS} fall records were found in available record history."
    assert len(response.citations) == MAX_FALL_CITATIONS
    assert repository.added_citations is not None
    assert len(repository.added_citations) == MAX_FALL_CITATIONS
    assert f"Only the {MAX_FALL_CITATIONS} most recent records are shown." in response.coverage_limitations


async def test_search_rejects_ai_mode_and_unimplemented_source_types():
    service = ResidentSearchService(StubSearchRepository(), InMemoryEventBus(), {})

    with pytest.raises(ValidationError, match="AI answer mode"):
        await service.search(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            ResidentSearchRequest(question="Show fall history", mode=SearchMode.AI_ANSWER),
        )

    with pytest.raises(ValidationError, match="incident"):
        await service.search(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            ResidentSearchRequest(question="Show incident history", source_types=[SearchSourceType.INCIDENT]),
        )


async def test_search_defaults_to_the_fall_adapter_when_source_type_is_omitted():
    care_home_id = uuid.uuid4()
    repository = StubSearchRepository([fall_citation()], scope=(care_home_id, uuid.uuid4()))

    response = await ResidentSearchService(repository, InMemoryEventBus(), fall_adapters(repository)).search(
        care_home_id,
        uuid.uuid4(),
        uuid.uuid4(),
        ResidentSearchRequest(question="Show the resident's fall history"),
    )

    assert response.citations[0].source_type is EvidenceSourceType.FALL


async def test_get_saved_search_rebuilds_the_cited_response_in_rank_order():
    resident_id = uuid.uuid4()
    search_id = uuid.uuid4()
    earlier = datetime(2026, 9, 1, tzinfo=UTC)
    later = datetime(2026, 10, 1, tzinfo=UTC)
    first_source_id = uuid.uuid4()
    second_source_id = uuid.uuid4()
    repository = StubSearchRepository()
    repository.persisted_search = SimpleNamespace(
        id=search_id,
        resident_id=resident_id,
        answer="Two falls were recorded in the selected period.",
        answer_status=AnswerStatus.SUPPORTED.value,
        coverage_limitations=["This result currently searches approved fall records only."],
        citations=[
            SimpleNamespace(
                source_type=SearchSourceType.FALL.value,
                source_id=second_source_id,
                source_version=earlier,
                occurred_at=earlier,
                title="Fall — no injury",
                excerpt="Location: lounge.",
                rank=2,
            ),
            SimpleNamespace(
                source_type=SearchSourceType.FALL.value,
                source_id=first_source_id,
                source_version=later,
                occurred_at=later,
                title="Fall — no injury",
                excerpt="Location: bedroom.",
                rank=1,
            ),
        ],
    )

    response = await ResidentSearchService(repository, InMemoryEventBus(), fall_adapters(repository)).get_saved_search(
        resident_id, search_id
    )

    assert response.search_id == search_id
    assert [citation.source_id for citation in response.citations] == [first_source_id, second_source_id]
    assert response.answer_status == AnswerStatus.SUPPORTED


async def test_get_source_requires_a_saved_citation_and_reports_source_changes():
    resident_id = uuid.uuid4()
    search_id = uuid.uuid4()
    source_id = uuid.uuid4()
    source_version_at_search = datetime(2026, 10, 1, 10, tzinfo=UTC)
    repository = StubSearchRepository()
    repository.scope = (uuid.uuid4(), uuid.uuid4())
    repository.persisted_citation = SimpleNamespace(source_version=source_version_at_search)
    repository.current_source = {
        "source_id": source_id,
        "occurred_at": source_version_at_search - timedelta(days=1),
        "source_version": source_version_at_search + timedelta(hours=1),
        "title": "Fall — no injury",
        "details": {"location": "Lounge"},
    }
    service = ResidentSearchService(repository, InMemoryEventBus(), fall_adapters(repository))

    response = await service.get_source(
        resident_id,
        search_id,
        SearchSourceType.FALL,
        source_id,
    )

    assert response.changed_since_search is True
    assert response.details == {"location": "Lounge"}

    repository.persisted_citation = None
    with pytest.raises(NotFoundError):
        await service.get_source(resident_id, search_id, SearchSourceType.FALL, source_id)


async def test_careplan_search_round_trips_revision_and_reopens_current_source():
    plan = plan_row()
    document = CarePlanEvidenceAdapter._document(plan=plan, goals=[])
    repository = StubSearchRepository(scope=(plan["care_home_id"], plan["floor_id"]))
    adapter = Mock(find=AsyncMock(return_value=[document]), get=AsyncMock(return_value=document))
    service = ResidentSearchService(repository, InMemoryEventBus(), {EvidenceSourceType.CARE_PLAN: adapter})
    response = await service.search(
        plan["care_home_id"],
        uuid.uuid4(),
        plan["resident_id"],
        ResidentSearchRequest(question="Show current mobility plan", source_types=[EvidenceSourceType.CARE_PLAN]),
    )
    assert response.citations[0].source_version == document.source_version
    assert response.answer == "1 care plan was found in available record history."
    assert any("historical plan versions are not included" in notice for notice in response.coverage_limitations)
    repository.persisted_search = SimpleNamespace(
        id=response.search_id,
        resident_id=plan["resident_id"],
        answer=response.answer,
        answer_status=response.answer_status.value,
        coverage_limitations=response.coverage_limitations,
        citations=[
            SimpleNamespace(
                **response.citations[0].model_dump(exclude={"evidence_id", "source_type"}),
                source_type=EvidenceSourceType.CARE_PLAN.value,
                rank=1,
            )
        ],
    )
    saved = await service.get_saved_search(plan["resident_id"], response.search_id)
    assert saved == response
    repository.persisted_citation = SimpleNamespace(source_version=document.source_version)
    source = await service.get_source(
        plan["resident_id"],
        response.search_id,
        EvidenceSourceType.CARE_PLAN,
        plan["care_plan_id"],
    )
    assert source.changed_since_search is False
    adapter.get.return_value = CarePlanEvidenceAdapter._document(
        plan=plan | {"content": "Changed instructions"}, goals=[]
    )
    changed = await service.get_source(
        plan["resident_id"],
        response.search_id,
        EvidenceSourceType.CARE_PLAN,
        plan["care_plan_id"],
    )
    assert changed.changed_since_search is True


async def test_legacy_timestamp_and_persisted_revision_token_do_not_report_false_change():
    repository = StubSearchRepository(scope=(uuid.uuid4(), uuid.uuid4()))
    when = datetime(2026, 10, 1, tzinfo=UTC)
    repository.persisted_citation = SimpleNamespace(source_version=revision_token(when))
    repository.current_source = {
        "occurred_at": when,
        "source_version": when,
        "title": "Fall",
        "details": {},
    }
    source = await ResidentSearchService(repository, InMemoryEventBus(), fall_adapters(repository)).get_source(
        uuid.uuid4(),
        uuid.uuid4(),
        EvidenceSourceType.FALL,
        uuid.uuid4(),
    )
    assert source.changed_since_search is False


class AssessmentAdapterStub:
    source_type = EvidenceSourceType.ASSESSMENT

    def __init__(self, document: EvidenceDocument):
        self.document = document
        self.get_calls: list[dict] = []

    async def find(self, **_kwargs):
        return [self.document]

    async def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return self.document


def mobility_assessment_document(
    *,
    resident_id: uuid.UUID,
    care_home_id: uuid.UUID,
    floor_id: uuid.UUID,
) -> EvidenceDocument:
    source_id = uuid.uuid4()
    assessed_at = datetime(2026, 10, 24, 10, tzinfo=UTC)
    return EvidenceDocument(
        evidence_id=f"mobility_assessment:{source_id}",
        source_type=EvidenceSourceType.MOBILITY_ASSESSMENT,
        source_id=source_id,
        resident_id=resident_id,
        care_home_id=care_home_id,
        floor_id=floor_id,
        authority_level=AuthorityLevel.FORMAL_ASSESSMENT,
        topic_tags={"mobility", "transfer"},
        status="assessed",
        occurred_at=assessed_at,
        time_precision="timestamp",
        effective_from=None,
        effective_to=None,
        source_version=assessed_at,
        title="Mobility assessment",
        searchable_text="Mobility assessment. Transfer method: standing hoist.",
        structured_metadata={"transfer_method": "standing hoist"},
        is_deleted=False,
        is_eligible=True,
    )


async def test_assessment_search_persists_concrete_assessment_citation():
    resident_id = uuid.uuid4()
    care_home_id = uuid.uuid4()
    floor_id = uuid.uuid4()
    document = mobility_assessment_document(
        resident_id=resident_id,
        care_home_id=care_home_id,
        floor_id=floor_id,
    )
    repository = StubSearchRepository(scope=(care_home_id, floor_id))
    adapter = AssessmentAdapterStub(document)
    service = ResidentSearchService(
        repository,
        InMemoryEventBus(),
        {EvidenceSourceType.ASSESSMENT: adapter},
    )

    response = await service.search(
        care_home_id,
        uuid.uuid4(),
        resident_id,
        ResidentSearchRequest(
            question="What is the latest mobility assessment?",
            source_types=[EvidenceSourceType.ASSESSMENT],
        ),
    )

    assert response.answer == "1 mobility assessment was found in available record history."
    assert response.citations[0].source_type is EvidenceSourceType.MOBILITY_ASSESSMENT
    assert repository.added_citations == response.citations


async def test_assessment_citation_reopens_through_its_group_adapter():
    resident_id = uuid.uuid4()
    care_home_id = uuid.uuid4()
    floor_id = uuid.uuid4()
    document = mobility_assessment_document(
        resident_id=resident_id,
        care_home_id=care_home_id,
        floor_id=floor_id,
    )
    repository = StubSearchRepository(scope=(care_home_id, floor_id))
    repository.persisted_citation = SimpleNamespace(source_version=document.source_version)
    adapter = AssessmentAdapterStub(document)
    service = ResidentSearchService(
        repository,
        InMemoryEventBus(),
        {EvidenceSourceType.ASSESSMENT: adapter},
    )

    response = await service.get_source(
        resident_id,
        uuid.uuid4(),
        EvidenceSourceType.MOBILITY_ASSESSMENT,
        document.source_id,
    )

    assert response.source_type is EvidenceSourceType.MOBILITY_ASSESSMENT
    assert response.details == {"transfer_method": "standing hoist"}
    assert adapter.get_calls == [
        {
            "resident_id": resident_id,
            "source_type": EvidenceSourceType.MOBILITY_ASSESSMENT,
            "source_id": document.source_id,
        }
    ]
