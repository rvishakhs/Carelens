import uuid

from app import InMemoryEventBus
from app.modules.resident_search.events import ResidentHistorySearched
from app.modules.resident_search.schemas import (
    EvidenceCitation,
    ResidentSearchRequest,
    SearchSourceType,
)
from app.modules.resident_search.service import ResidentSearchService


class StubSearchRepository:
    def __init__(self, evidence: list[EvidenceCitation], *, exists: bool = True):
        self._evidence = evidence
        self._exists = exists

    async def resident_exists(self, resident_id: uuid.UUID) -> bool:
        return self._exists

    async def find_falls(self, resident_id, from_date, to_date):
        return self._evidence


async def test_search_publishes_metadata_only_audit_event():
    resident_id = uuid.uuid4()
    care_home_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    evidence = [
        EvidenceCitation(
            evidence_id=f"fall:{uuid.uuid4()}",
            source_type=SearchSourceType.FALL,
            source_id=uuid.uuid4(),
            occurred_at="2026-10-01T10:00:00Z",
            title="Fall — no injury",
            excerpt="Location: lounge.",
        )
    ]
    event_bus = InMemoryEventBus()
    events: list[ResidentHistorySearched] = []

    async def capture(event: ResidentHistorySearched) -> None:
        events.append(event)

    event_bus.subscribe(ResidentHistorySearched, capture)
    service = ResidentSearchService(StubSearchRepository(evidence), event_bus)

    response = await service.search(
        care_home_id,
        actor_id,
        resident_id,
        ResidentSearchRequest(query="Show the resident's fall history"),
    )

    assert response.evidence == evidence
    assert len(events) == 1
    event = events[0]
    assert event.care_home_id == care_home_id
    assert event.actor_user_id == actor_id
    assert event.resident_id == resident_id
    assert event.result_count == 1
    # The event reaches the audit subscriber, so it must not contain query text or
    # clinical excerpts that would duplicate sensitive information in audit storage.
    assert "query" not in event.model_dump()
    assert "excerpt" not in event.model_dump()
