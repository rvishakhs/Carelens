from datetime import UTC, datetime, timedelta

from app import AuditRepository, rls_session
from app.main import app
from app.modules.resident_search.repository import ResidentSearchRepository
from app.modules.resident_search.schemas import ResidentSearchRequest
from app.modules.resident_search.service import ResidentSearchService
from tests.integration.test_clinical_observation_feed import clinical_home, insert_source


async def test_resident_history_search_writes_append_only_audit_event(clinical_home):
    home, actor, floors, residents = clinical_home
    resident_id = residents[0]
    await insert_source(
        clinical_home,
        "falls_incidents",
        {
            "severity": "no_injury",
            "occurred_at": datetime.now(UTC) - timedelta(days=1),
            "location": "Lounge",
        },
    )

    async with rls_session(home, actor, [floors[0]]) as session:
        service = ResidentSearchService(ResidentSearchRepository(session), app.state.container.event_bus)
        result = await service.search(
            home,
            actor,
            resident_id,
            ResidentSearchRequest(query="Show the fall history", source_types=["fall"]),
        )

    assert len(result.evidence) == 1
    assert result.evidence[0].source_type == "fall"

    async with rls_session(home, actor, [floors[0]]) as session:
        events = await AuditRepository(session).list_events(entity_type="resident_history_search")

    assert len(events) == 1
    event = events[0]
    assert event.action.value == "view"
    assert event.actor_id == actor
    assert event.entity_id == resident_id
    assert event.justification is None
