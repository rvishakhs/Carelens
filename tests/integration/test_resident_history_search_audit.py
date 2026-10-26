import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app import AuditRepository, rls_session
from app.main import app
from app.modules.resident_search.evidence.falls import FallsEvidenceAdapter
from app.modules.resident_search.repository import ResidentSearchRepository
from app.modules.resident_search.schemas import ResidentSearchRequest, SearchSourceType
from app.modules.resident_search.service import ResidentSearchService
from tests.integration.test_clinical_observation_feed import insert_source

pytest_plugins = ("tests.integration.test_clinical_observation_feed",)


async def test_resident_history_search_persists_citations_and_writes_append_only_audit_event(clinical_home):
    home, actor, floors, residents = clinical_home
    resident_id = residents[0]
    occurred_at = datetime.now(UTC) - timedelta(days=1)
    source_id = await insert_source(
        clinical_home,
        "falls_incidents",
        {
            "severity": "no_injury",
            "occurred_at": occurred_at,
            "location": "Lounge",
        },
    )

    async with rls_session(home, actor, [floors[0]]) as session:
        repository = ResidentSearchRepository(session)
        service = ResidentSearchService(
            repository,
            app.state.container.event_bus,
            {SearchSourceType.FALL: FallsEvidenceAdapter(session)},
        )
        result = await service.search(
            home,
            actor,
            resident_id,
            ResidentSearchRequest(
                question="Show the resident's fall history",
                from_date=occurred_at - timedelta(minutes=1),
                to_date=occurred_at + timedelta(minutes=1),
                source_types=[SearchSourceType.FALL],
            ),
        )
        saved_result = await service.get_saved_search(resident_id, result.search_id)
        source = await service.get_source(
            resident_id,
            result.search_id,
            SearchSourceType.FALL,
            source_id,
        )

    assert result.answer_status.value == "supported"
    assert len(result.citations) == 1
    assert result.citations[0].source_type == SearchSourceType.FALL
    assert result.citations[0].source_id == source_id
    assert saved_result == result
    assert source.source_id == source_id
    assert source.changed_since_search is False
    assert source.details["location"] == "Lounge"

    async with rls_session(home, actor, [floors[0]]) as session:
        events = await AuditRepository(session).list_events(entity_type="resident_history_search")

    assert len(events) == 1
    event = events[0]
    assert event.action.value == "view"
    assert event.actor_id == actor
    assert event.entity_id == resident_id
    assert event.justification is None


async def test_resident_history_search_http_contract_and_current_source_endpoint(client, clinical_home):
    resident_id = clinical_home[3][0]
    source_id = await insert_source(
        clinical_home,
        "falls_incidents",
        {
            "severity": "no_injury",
            "occurred_at": datetime.now(UTC) - timedelta(hours=2),
            "location": "Dining room",
        },
    )

    created = await client.post(
        f"/residents/{resident_id}/history-search",
        json={
            "question": "What is the fall history?",
            "source_types": ["fall"],
        },
    )

    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    result = created.json()
    assert result["answer_status"] == "supported"
    assert result["citations"][0]["source_id"] == str(source_id)
    assert result["citations"][0]["source_type"] == "fall"

    search_id = result["search_id"]
    fetched = await client.get(f"/residents/{resident_id}/history-search/{search_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.headers["cache-control"] == "no-store"
    assert fetched.json() == result

    source = await client.get(f"/residents/{resident_id}/history-search/{search_id}/sources/fall/{source_id}")
    assert source.status_code == 200, source.text
    assert source.headers["cache-control"] == "no-store"
    assert source.json()["changed_since_search"] is False
    assert source.json()["details"]["location"] == "Dining room"

    home, actor, floors, _ = clinical_home
    async with rls_session(home, actor, [floors[0]]) as session:
        await session.execute(
            text("UPDATE falls_incidents SET action_taken = 'Nurse reviewed' WHERE id = :id"), {"id": source_id}
        )
    source_url = f"/residents/{resident_id}/history-search/{search_id}/sources/fall/{source_id}"
    changed = await client.get(source_url)
    assert changed.status_code == 200
    assert changed.json()["changed_since_search"] is True
    assert changed.json()["details"]["action_taken"] == "Nurse reviewed"
    async with rls_session(home, actor, [floors[0]]) as session:
        await session.execute(text("UPDATE falls_incidents SET deleted_at = now() WHERE id = :id"), {"id": source_id})
    assert (await client.get(source_url)).status_code == 404


async def test_resident_history_search_allows_appointments_but_rejects_unimplemented_source_types(client, clinical_home):
    resident_id = clinical_home[3][0]
    appointment_response = await client.post(
        f"/residents/{resident_id}/history-search",
        json={
            "question": "What was the last hospital appointment?",
            "source_types": ["appointment"],
        },
    )

    assert appointment_response.status_code == 201
    assert appointment_response.json()["answer_status"] == "no_evidence"

    response = await client.post(
        f"/residents/{resident_id}/history-search",
        json={"question": "Show incident history", "source_types": ["incident"]},
    )
    assert response.status_code == 422
    assert "incident" in response.json()["message"]


async def test_falls_adapter_date_boundaries_limit_and_deleted_sources(clinical_home):
    home, actor, floors, residents = clinical_home
    when = datetime(2026, 10, 1, tzinfo=UTC)
    ids = [
        await insert_source(
            clinical_home,
            "falls_incidents",
            {
                "occurred_at": when + timedelta(days=index),
                "severity": "no_injury",
                "location": "Lounge",
            },
        )
        for index in range(3)
    ]
    async with rls_session(home, actor, [floors[0]]) as session:
        adapter = FallsEvidenceAdapter(session)
        docs = await adapter.find(resident_id=residents[0], from_date=when, to_date=when + timedelta(days=2), limit=1)
        assert [doc.source_id for doc in docs] == [ids[1]]
        assert docs[0].floor_id == floors[0]
        await session.execute(text("UPDATE falls_incidents SET deleted_at = now() WHERE id = :id"), {"id": ids[1]})
        assert await adapter.get(resident_id=residents[0], source_id=ids[1]) is None
        docs = await adapter.find(resident_id=residents[0], from_date=when, to_date=when + timedelta(days=2), limit=50)
        assert [doc.source_id for doc in docs] == [ids[0]]


async def test_falls_adapter_and_http_deny_other_residents_floors_and_homes(client, clinical_home):
    home, actor, floors, residents = clinical_home
    source_id = await insert_source(
        clinical_home,
        "falls_incidents",
        {
            "occurred_at": datetime.now(UTC),
            "severity": "no_injury",
        },
        resident_index=1,
    )
    async with rls_session(home, actor, [floors[0]]) as session:
        adapter = FallsEvidenceAdapter(session)
        assert await adapter.find(resident_id=residents[1], from_date=None, to_date=None, limit=50) == []
        assert await adapter.get(resident_id=residents[1], source_id=source_id) is None
        assert await adapter.get(resident_id=residents[0], source_id=source_id) is None
    async with rls_session(uuid.uuid4(), actor, floors) as session:
        assert await FallsEvidenceAdapter(session).get(resident_id=residents[1], source_id=source_id) is None
    response = await client.post(f"/residents/{residents[1]}/history-search", json={"question": "Fall history"})
    assert response.status_code == 404


@pytest.mark.parametrize("role", ["carer", "family", "emergency"])
async def test_fall_search_http_requires_current_permission(client, clinical_home, role):
    from app import CurrentUser, Role, get_current_user

    home, actor, floors, residents = clinical_home
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=actor,
        care_home_id=home,
        care_home_name="Test",
        role=Role(role),
        email="test@example.com",
        display_name="Test",
        floor_ids=[floors[0]],
    )
    response = await client.post(f"/residents/{residents[0]}/history-search", json={"question": "Fall history"})
    assert response.status_code == 403
