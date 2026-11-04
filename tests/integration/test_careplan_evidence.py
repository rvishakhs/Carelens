"""Care-plan evidence and revision storage against migrated PostgreSQL/RLS."""

import importlib
import uuid
from datetime import UTC, datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app import rls_session
from app.modules.resident_search.evidence.careplan import CarePlanEvidenceAdapter
from app.modules.resident_search.evidence.revisions import revision_token
from tests.integration.test_clinical_observation_feed import (
    client as client,
)
from tests.integration.test_clinical_observation_feed import (
    clinical_home as clinical_home,
)
from tests.integration.test_clinical_observation_feed import (
    insert_source,
)


async def seed_plan(context, *, resident_index=0, domain="mobility"):
    plan_id = await insert_source(
        context,
        "care_plans",
        {
            "domain": domain,
            "goal": "Maintain safe transfers",
            "current_version": 2,
        },
        resident_index=resident_index,
    )
    home, actor, floors, _ = context
    async with rls_session(home, actor, floors) as session:
        for number, content in ((1, "Superseded instructions"), (2, "Use standing aid with two staff")):
            await session.execute(
                text("""
                INSERT INTO care_plan_versions
                    (id, care_home_id, care_plan_id, version_number, content, created_at)
                VALUES (:id, :home, :plan, :version, :content, :when)
            """),
                {
                    "id": uuid.uuid4(),
                    "home": home,
                    "plan": plan_id,
                    "version": number,
                    "content": content,
                    "when": datetime(2026, 1, number, tzinfo=UTC),
                },
            )
    goal_id = await insert_source(
        context,
        "care_plan_goals",
        {
            "care_plan_id": plan_id,
            "goal_text": "Maintain comfort",
            "status": "in_progress",
        },
        resident_index=resident_index,
    )
    return plan_id, goal_id


async def test_current_version_goals_and_current_dates(clinical_home):
    home, actor, floors, residents = clinical_home
    plan_id, goal_id = await seed_plan(clinical_home)
    async with rls_session(home, actor, floors) as session:
        adapter = CarePlanEvidenceAdapter(session)
        documents = await adapter.find(
            resident_id=residents[0],
            from_date=datetime(2026, 10, 1, tzinfo=UTC),
            to_date=datetime(2026, 11, 1, tzinfo=UTC),
            topics={"transfer"},
            limit=1,
        )
        assert len(documents) == 1
        document = documents[0]
        assert document.source_id == plan_id
        assert "Use standing aid with two staff" in document.searchable_text
        assert "Superseded instructions" not in document.searchable_text
        assert document.structured_metadata["version_number"] == 2
        assert document.structured_metadata["goals"][0]["id"] == goal_id
        assert document.effective_from is None
        assert await adapter.get(resident_id=residents[0], source_id=plan_id) == document


@pytest.mark.parametrize("table", ["care_plans", "care_plan_versions"])
async def test_deleted_plan_or_current_version_is_not_retrievable(clinical_home, table):
    home, actor, floors, residents = clinical_home
    plan_id, _ = await seed_plan(clinical_home)
    async with rls_session(home, actor, floors) as session:
        if table == "care_plans":
            await session.execute(text("UPDATE care_plans SET deleted_at = now() WHERE id = :id"), {"id": plan_id})
        else:
            await session.execute(
                text("""
                UPDATE care_plan_versions SET deleted_at = now()
                WHERE care_plan_id = :id AND version_number = 2
            """),
                {"id": plan_id},
            )
        adapter = CarePlanEvidenceAdapter(session)
        assert await adapter.find(resident_id=residents[0], from_date=None, to_date=None, limit=10) == []
        assert await adapter.get(resident_id=residents[0], source_id=plan_id) is None


async def test_inactive_plan_and_deleted_goal_handling(clinical_home):
    home, actor, floors, residents = clinical_home
    plan_id, goal_id = await seed_plan(clinical_home)
    async with rls_session(home, actor, floors) as session:
        adapter = CarePlanEvidenceAdapter(session)
        before = await adapter.get(resident_id=residents[0], source_id=plan_id)
        await session.execute(text("UPDATE care_plan_goals SET deleted_at = now() WHERE id = :id"), {"id": goal_id})
        after = await adapter.get(resident_id=residents[0], source_id=plan_id)
        assert after.source_version != before.source_version
        assert after.structured_metadata["goals"] == []
        await session.execute(text("UPDATE care_plans SET is_active = false WHERE id = :id"), {"id": plan_id})
        assert await adapter.get(resident_id=residents[0], source_id=plan_id) is None


async def test_wrong_resident_floor_home_and_unscoped_sessions_cannot_read_plan(clinical_home):
    home, actor, floors, residents = clinical_home
    plan_id, _ = await seed_plan(clinical_home, resident_index=1)
    for scoped_home, scoped_floors in ((home, [floors[0]]), (uuid.uuid4(), floors), (home, [])):
        async with rls_session(scoped_home, actor, scoped_floors) as session:
            adapter = CarePlanEvidenceAdapter(session)
            assert await adapter.get(resident_id=residents[1], source_id=plan_id) is None
            assert await adapter.find(resident_id=residents[1], from_date=None, to_date=None, limit=10) == []
    async with rls_session(home, actor, floors) as session:
        assert await CarePlanEvidenceAdapter(session).get(resident_id=residents[0], source_id=plan_id) is None


async def test_mismatched_resident_goal_is_not_attached_to_plan(clinical_home):
    home, actor, floors, residents = clinical_home
    plan_id, goal_id = await seed_plan(clinical_home)
    await insert_source(
        clinical_home,
        "care_plan_goals",
        {
            "care_plan_id": plan_id,
            "goal_text": "Different resident's goal",
        },
        resident_index=1,
    )
    async with rls_session(home, actor, floors) as session:
        document = await CarePlanEvidenceAdapter(session).get(resident_id=residents[0], source_id=plan_id)
        assert [goal["id"] for goal in document.structured_metadata["goals"]] == [goal_id]


async def test_http_search_persists_hash_reopens_source_and_detects_goal_changes(client, clinical_home):
    home, actor, floors, residents = clinical_home
    plan_id, goal_id = await seed_plan(clinical_home)
    resident_id = residents[0]
    created = await client.post(
        f"/residents/{resident_id}/history-search",
        json={
            "question": "Show current mobility care plan",
            "source_types": ["care_plan"],
            "from": "2026-10-01T00:00:00Z",
            "to": "2026-11-01T00:00:00Z",
        },
    )
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["citations"][0]["source_version"].startswith("sha256:")
    assert any("current active versions" in notice for notice in result["coverage_limitations"])
    result_url = f"/residents/{resident_id}/history-search/{result['search_id']}"
    assert (await client.get(result_url)).json() == result
    source_url = f"{result_url}/sources/care_plan/{plan_id}"
    source = await client.get(source_url)
    assert source.status_code == 200, source.text
    assert source.json()["changed_since_search"] is False

    async with rls_session(home, actor, floors) as session:
        await session.execute(text("UPDATE care_plan_goals SET status = 'achieved' WHERE id = :id"), {"id": goal_id})
    changed = await client.get(source_url)
    assert changed.status_code == 200, changed.text
    assert changed.json()["changed_since_search"] is True
    assert changed.json()["details"]["goals"][0]["status"] == "achieved"
    # Saved evidence remains the original snapshot, while reopening returns current details.
    assert (await client.get(result_url)).json() == result
    async with rls_session(home, actor, floors) as session:
        await session.execute(text("UPDATE care_plans SET is_active = false WHERE id = :id"), {"id": plan_id})
    assert (await client.get(source_url)).status_code == 404


def run_revision_migration(sync_session, direction):
    migration = importlib.import_module("migrations.versions.0034_search_citation_revision_tokens")
    with Operations.context(MigrationContext.configure(sync_session.connection())):
        getattr(migration, direction)()


async def test_revision_migration_preserves_legacy_timestamps_and_nulls(clinical_home):
    home, actor, floors, _ = clinical_home
    when = datetime(2026, 1, 1, 10, 30, 0, 123456, tzinfo=UTC)
    async with rls_session(home, actor, floors) as session:
        # A transaction-local table shadows the real table so migration data
        # conversion can be exercised without altering any application records.
        await session.execute(
            text("""
            CREATE TEMP TABLE resident_history_search_citations (source_version TIMESTAMPTZ)
            ON COMMIT DROP
        """)
        )
        await session.execute(
            text("""
            INSERT INTO resident_history_search_citations VALUES (:when), (NULL)
        """),
            {"when": when},
        )
        await session.execute(text("SELECT set_config('TimeZone', 'Asia/Kolkata', true)"))
        await session.run_sync(lambda sync: run_revision_migration(sync, "upgrade"))
        values = (
            (await session.execute(text("SELECT source_version FROM resident_history_search_citations")))
            .scalars()
            .all()
        )
        assert values == [revision_token(when), None]
        await session.run_sync(lambda sync: run_revision_migration(sync, "downgrade"))
        values = (
            (await session.execute(text("SELECT source_version FROM resident_history_search_citations")))
            .scalars()
            .all()
        )
        assert values == [when, None]


async def test_revision_downgrade_refuses_to_discard_hashes(clinical_home):
    home, actor, floors, _ = clinical_home
    async with rls_session(home, actor, floors) as session:
        await session.execute(
            text("""
            CREATE TEMP TABLE resident_history_search_citations (source_version TEXT)
            ON COMMIT DROP
        """)
        )
        await session.execute(text("INSERT INTO resident_history_search_citations VALUES ('sha256:example')"))
        with pytest.raises(DBAPIError, match="Cannot downgrade"):
            async with session.begin_nested():
                await session.run_sync(lambda sync: run_revision_migration(sync, "downgrade"))
        assert (
            await session.execute(text("SELECT source_version FROM resident_history_search_citations"))
        ).scalar_one() == ("sha256:example")
