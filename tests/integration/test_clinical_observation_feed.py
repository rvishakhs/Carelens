"""Exercise the migrated source tables through real RLS and HTTP dependencies."""

import asyncio
import random
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app import (
    CareHome,
    CurrentUser,
    FakeLLMProvider,
    Floor,
    Resident,
    Role,
    User,
    get_current_user,
    rls_session,
    system_session,
)
from app.main import app
from app.modules.observations.repository import ObservationRepository
from synthdata.home_setup import build_care_home


async def _make_home():
    home, actor = uuid.uuid4(), uuid.uuid4()
    async with rls_session(home, actor) as session:
        session.add(CareHome(**{**build_care_home(random.Random(home.int), "Clinical feed test"), "id": home}))
        await session.flush()
        session.add(
            User(
                id=actor,
                care_home_id=home,
                oidc_subject=str(actor),
                email="test@example.com",
                display_name="Test Nurse",
                role=Role.NURSE,
            )
        )
        floors = [Floor(care_home_id=home, name=name) for name in ("A", "B")]
        session.add_all(floors)
        await session.flush()
        floor_ids = [floor.id for floor in floors]
    async with rls_session(home, actor, floor_ids) as session:
        residents = [
            Resident(
                care_home_id=home,
                floor_id=floor,
                first_name="Test",
                last_name="Resident",
                date_of_birth=date(1945, 1, 1),
                admission_date=date.today(),
            )
            for floor in floor_ids
        ]
        session.add_all(residents)
        await session.flush()
        resident_ids = [resident.id for resident in residents]
    return home, actor, floor_ids, resident_ids


@pytest.fixture
async def clinical_home():
    return await _make_home()


@pytest.fixture
async def client(clinical_home, monkeypatch):
    home, actor, floors, _ = clinical_home
    user = CurrentUser(
        id=actor,
        care_home_id=home,
        care_home_name="Test",
        role=Role.NURSE,
        email="test@example.com",
        display_name="Test Nurse",
        floor_ids=[floors[0]],
    )
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(app.state.container, "llm_provider", FakeLLMProvider())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def insert_source(context, table, values, resident_index=0):
    home, actor, floors, residents = context
    data = {"id": uuid.uuid4(), "care_home_id": home, "resident_id": residents[resident_index], **values}
    async with rls_session(home, actor, floors) as session:
        await session.execute(
            text(f"INSERT INTO {table} ({', '.join(data)}) VALUES ({', '.join(':' + key for key in data)})"), data
        )
    return data["id"]


CASES = [
    ("fluid_intake_records", {"volume_ml": 275}, "recorded_at", "fluid_intake", "ml", 275),
    (
        "food_intake_records",
        {"meal_type": "lunch", "percentage_eaten": 75},
        "recorded_at",
        "meal",
        "fraction_eaten",
        0.75,
    ),
    ("weight_records", {"weight_kg": 70.5}, "recorded_at", "weight", "kg", 70.5),
    (
        "vital_signs_records",
        {"temperature_celsius": 37.2, "oxygen_saturation_pct": 96},
        "recorded_at",
        "vitals",
        "temperature_c",
        37.2,
    ),
    (
        "mobility_observations",
        {"activity": "Walked with assistance"},
        "recorded_at",
        "mobility",
        "activity",
        "Walked with assistance",
    ),
    ("continence_records", {"event_type": "continent"}, "recorded_at", "continence", "event_type", "continent"),
    ("wellbeing_records", {"mood": "settled"}, "recorded_at", "wellbeing", "mood", "settled"),
    (
        "behaviour_records",
        {"behaviour_type": "wandering", "behaviour_description": "Walking in corridor"},
        "occurred_at",
        "behaviour",
        "behaviour_description",
        "Walking in corridor",
    ),
    (
        "communication_logs",
        {"interaction_summary": "Asked to phone family"},
        "recorded_at",
        "communication",
        "interaction_summary",
        "Asked to phone family",
    ),
    ("sleep_records", {"quality": "restless"}, "night_of", "sleep", "quality", "restless"),
    ("pain_assessments", {"scale_type": "self_report_0_10", "score": 3}, "assessed_at", "pain", "score", 3),
    ("falls_incidents", {"severity": "no_injury"}, "occurred_at", "fall", "severity", "no_injury"),
    (
        "incidents",
        {"incident_type": "near_miss", "description": "Trip avoided"},
        "occurred_at",
        "incident",
        "description",
        "Trip avoided",
    ),
    ("wound_records", {"body_location": "Left heel"}, "first_observed", "wound", "body_location", "Left heel"),
]


@pytest.mark.parametrize("table,values,time_column,kind,key,expected", CASES)
async def test_historical_source_round_trip(client, clinical_home, table, values, time_column, kind, key, expected):
    when = datetime.now(UTC) - timedelta(hours=1)
    date_only = time_column in ("night_of", "first_observed")
    source_id = await insert_source(clinical_home, table, {**values, time_column: when.date() if date_only else when})
    response = await client.get("/observations", params={"resident_id": str(clinical_home[3][0]), "type": kind})
    assert response.status_code == 200, response.text
    (item,) = response.json()
    assert item["id"] == str(source_id)
    assert item["source_type"] == table
    assert item["value"][key] == expected
    assert item["is_implausible"] is False
    if date_only:
        assert item["time_precision"] == "date"
        assert item["source_date"] == when.date().isoformat()
        midnight = datetime.combine(when.date(), datetime.min.time(), ZoneInfo("Europe/London"))
        assert datetime.fromisoformat(item["recorded_at"]) == midnight
    else:
        assert datetime.fromisoformat(item["recorded_at"]) == when
    detail = await client.get(
        f"/observations/sources/{table}/{source_id}", params={"resident_id": str(clinical_home[3][0])}
    )
    assert detail.json() == item


async def test_native_post_is_visible_once_and_retries_conflict(client, clinical_home):
    rid = str(clinical_home[3][0])
    payload = {
        "resident_id": rid,
        "type": "note",
        "value": {"text": "Settled after lunch"},
        "recorded_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        "idempotency_key": "one",
    }
    created = await client.post("/observations", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["source_type"] == "observations"
    replay = await client.post("/observations", json=payload)
    assert replay.status_code == 409, replay.text
    history = await client.get("/observations", params={"resident_id": rid})
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == created.json()["id"]
    assert history.json()[0]["value"]["structured"]["mood"] == "settled"


async def test_period_pagination_deletion_and_source_collision(client, clinical_home):
    when = datetime.now(UTC) - timedelta(hours=2)
    shared_id = uuid.uuid4()
    fluid = await insert_source(
        clinical_home, "fluid_intake_records", {"id": shared_id, "volume_ml": 200, "recorded_at": when}
    )
    await insert_source(clinical_home, "weight_records", {"id": shared_id, "weight_kg": 65, "recorded_at": when})
    await insert_source(
        clinical_home, "fluid_intake_records", {"volume_ml": 400, "recorded_at": when - timedelta(days=2)}
    )
    await insert_source(
        clinical_home, "fluid_intake_records", {"volume_ml": 999, "recorded_at": when, "deleted_at": when}
    )
    await insert_source(
        clinical_home, "fluid_intake_records", {"volume_ml": 900, "recorded_at": when + timedelta(hours=1)}
    )
    params = {
        "resident_id": str(clinical_home[3][0]),
        "since": when.isoformat(),
        "until": (when + timedelta(hours=1)).isoformat(),
        "limit": 1,
    }
    first = (await client.get("/observations", params=params)).json()
    second = (await client.get("/observations", params={**params, "offset": 1})).json()
    assert first[0]["id"] == second[0]["id"] == str(shared_id)
    assert first[0]["source_type"] != second[0]["source_type"]
    assert (await client.get("/observations", params={**params, "offset": 2})).json() == []
    home, actor, floors, residents = clinical_home
    async with rls_session(home, actor, floors) as session:
        await session.execute(text("UPDATE fluid_intake_records SET volume_ml=250 WHERE id=:id"), {"id": fluid})
    detail = await client.get(
        f"/observations/sources/fluid_intake_records/{fluid}", params={"resident_id": str(residents[0])}
    )
    assert detail.json()["value"]["ml"] == 250
    async with rls_session(home, actor, floors) as session:
        await session.execute(text("UPDATE fluid_intake_records SET deleted_at=now() WHERE id=:id"), {"id": fluid})
    assert (
        await client.get(
            f"/observations/sources/fluid_intake_records/{fluid}", params={"resident_id": str(residents[0])}
        )
    ).status_code == 404


async def test_floor_and_no_context_isolation(client, clinical_home):
    hidden = await insert_source(clinical_home, "fluid_intake_records", {"volume_ml": 300}, resident_index=1)
    rid = clinical_home[3][1]
    assert (await client.get("/observations", params={"resident_id": str(rid)})).json() == []
    assert (
        await client.get(f"/observations/sources/fluid_intake_records/{hidden}", params={"resident_id": str(rid)})
    ).status_code == 404
    async with system_session() as session:
        assert await ObservationRepository(session).list_for_resident(rid) == []


async def test_summary_and_handover_use_historical_sources(client, clinical_home):
    source_id = await insert_source(
        clinical_home, "fluid_intake_records", {"volume_ml": 250, "recorded_at": datetime.now(UTC) - timedelta(hours=1)}
    )
    rid = str(clinical_home[3][0])
    generated = await client.post(f"/summaries/{rid}/generate")
    assert generated.status_code == 201, generated.text
    assert generated.json()["input_record_refs"] == [{"table": "fluid_intake_records", "id": str(source_id)}]
    assert generated.json()["source_observation_ids"] == [str(source_id)]
    handover = await client.get("/handover")
    assert handover.status_code == 200, handover.text
    (card,) = handover.json()
    assert card["latest_summary"]["id"] == generated.json()["id"]
    assert card["recent_observations"][0]["source_type"] == "fluid_intake_records"
    feedback = await client.post(f"/summaries/{generated.json()['id']}/feedback", json={"rating": "thumbs_up"})
    assert feedback.status_code == 200, feedback.text
    assert feedback.json()["feedback_rating"] == "thumbs_up"


@pytest.mark.parametrize(
    "kind,value",
    [
        ("fluid_intake", {"ml": 200}),
        ("weight", {"kg": 70}),
        ("vitals", {"heart_rate_bpm": 80}),
        ("meal", {"meal": "lunch", "fraction_eaten": 0.5}),
        ("mobility", {"activity": "Walked"}),
        ("note", {"text": "Resident settled"}),
    ],
)
async def test_native_types_can_be_saved_and_read(client, clinical_home, kind, value):
    rid = str(clinical_home[3][0])
    created = await client.post(
        "/observations",
        json={
            "resident_id": rid,
            "type": kind,
            "value": value,
            "recorded_at": datetime.now(UTC).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    result = await client.get("/observations", params={"resident_id": rid, "type": kind})
    assert result.status_code == 200, result.text
    assert result.json()[0]["type"] == kind
    assert result.json()[0]["source_type"] == "observations"


async def test_all_domain_sources_deny_other_floor_and_tenant(client, clinical_home):
    other = await _make_home()
    now = datetime.now(UTC) - timedelta(hours=1)
    for table, values, time_column, *_ in CASES:
        values = {**values, time_column: now.date() if time_column in ("night_of", "first_observed") else now}
        for context, index in ((clinical_home, 1), (other, 0)):
            source_id = await insert_source(context, table, values, resident_index=index)
            hidden = str(context[3][index])
            response = await client.get(f"/observations/sources/{table}/{source_id}", params={"resident_id": hidden})
            assert response.status_code == 404, response.text
    for hidden in (clinical_home[3][1], other[3][0]):
        assert (await client.get("/observations", params={"resident_id": str(hidden)})).json() == []
        denied = await client.post(
            "/observations",
            json={
                "resident_id": str(hidden),
                "type": "note",
                "value": {"text": "Must not save"},
                "recorded_at": now.isoformat(),
            },
        )
        assert denied.status_code == 404, denied.text
    # Native rows also need DB enforcement when the application repository is bypassed.
    home, actor, floors, residents = other
    async with rls_session(home, actor, floors) as session:
        from app import Observation

        session.add(
            Observation(
                care_home_id=home,
                resident_id=residents[0],
                type="note",
                value={"text": "Other home"},
                recorded_at=now,
                recorded_by=actor,
            )
        )
        await session.flush()
    assert (await client.get("/observations", params={"resident_id": str(residents[0])})).json() == []
    async with system_session() as session:
        assert (await session.execute(text("SELECT id FROM observations"))).all() == []
        assert (await session.execute(text("SELECT id FROM pseudonym_mappings"))).all() == []


async def test_batch_rollback_and_concurrent_duplicate_retry(client, clinical_home):
    rid = str(clinical_home[3][0])
    payload = {
        "resident_id": rid,
        "type": "note",
        "value": {"text": "One entry"},
        "recorded_at": datetime.now(UTC).isoformat(),
        "idempotency_key": "concurrent",
    }
    responses = await asyncio.gather(
        client.post("/observations", json=payload), client.post("/observations", json=payload)
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    history = await client.get("/observations", params={"resident_id": rid})
    assert len(history.json()) == 1
    batch = [{**payload, "idempotency_key": "batch"}, {**payload, "resident_id": str(uuid.uuid4())}]
    failed = await client.post("/observations/batch", json=batch)
    assert failed.status_code == 404, failed.text
    assert len((await client.get("/observations", params={"resident_id": rid})).json()) == 1
    success = await client.post(
        "/observations/batch",
        json=[
            {**payload, "idempotency_key": "batch-1"},
            {**payload, "idempotency_key": "batch-2"},
        ],
    )
    assert success.status_code == 201, success.text
    assert len(success.json()) == 2


async def test_invalid_filters_and_read_only_types_are_rejected(client, clinical_home):
    rid = str(clinical_home[3][0])
    for params in (
        {"limit": 0},
        {"offset": -1},
        {"since": "2026-09-08T12:00:00"},
        {"since": "2026-09-09T00:00:00Z", "until": "2026-09-08T00:00:00Z"},
    ):
        response = await client.get("/observations", params={"resident_id": rid, **params})
        assert response.status_code == 422, response.text
    for kind in ("fall", "wellbeing", "sleep"):
        response = await client.post(
            "/observations",
            json={
                "resident_id": rid,
                "type": kind,
                "value": {},
                "recorded_at": datetime.now(UTC).isoformat(),
            },
        )
        assert response.status_code == 422, response.text


async def test_deleted_resident_sources_are_hidden(client, clinical_home):
    source_id = await insert_source(clinical_home, "fluid_intake_records", {"volume_ml": 300})
    home, actor, floors, residents = clinical_home
    async with rls_session(home, actor, floors) as session:
        await session.execute(text("UPDATE residents SET deleted_at=now() WHERE id=:id"), {"id": residents[0]})
    assert (await client.get("/observations", params={"resident_id": str(residents[0])})).json() == []
    assert (
        await client.get(
            f"/observations/sources/fluid_intake_records/{source_id}", params={"resident_id": str(residents[0])}
        )
    ).status_code == 404


async def test_recent_reader_has_no_display_cap_and_excludes_future(clinical_home):
    home, actor, floors, residents = clinical_home
    now = datetime.now(UTC)
    async with rls_session(home, actor, floors) as session:
        await session.execute(
            text("""
            INSERT INTO fluid_intake_records (care_home_id, resident_id, volume_ml, recorded_at)
            SELECT :home, :resident, 10, CAST(:when AS timestamptz)
            FROM generate_series(1, 105)
        """),
            {"home": home, "resident": residents[0], "when": now - timedelta(hours=1)},
        )
    await insert_source(
        clinical_home, "fluid_intake_records", {"volume_ml": 999, "recorded_at": now + timedelta(days=1)}
    )
    async with rls_session(home, actor, [floors[0]]) as session:
        rows = await ObservationRepository(session).get_recent_for_resident(residents[0])
        assert len(rows) == 105
        assert all(row.value["ml"] == 10 for row in rows)
        assert await ObservationRepository(session).get_recent_for_residents([]) == {}


async def test_native_storage_rejects_unscoped_and_wrong_floor_writes(clinical_home):
    from sqlalchemy.exc import DBAPIError

    home, actor, floors, residents = clinical_home
    sql = text("""
        INSERT INTO observations (care_home_id, resident_id, type, value, recorded_at, recorded_by)
        VALUES (:home, :resident, 'note', '{"text":"not permitted"}', now(), :actor)
    """)
    with pytest.raises(DBAPIError):
        async with rls_session(home, actor, [floors[0]]) as session:
            await session.execute(sql, {"home": home, "resident": residents[1], "actor": actor})
    with pytest.raises(DBAPIError):
        async with system_session() as session:
            await session.execute(sql, {"home": home, "resident": residents[0], "actor": actor})
