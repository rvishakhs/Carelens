import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.modules.resident_search.evidence.careplan import CarePlanEvidenceAdapter
from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceSourceType
from app.modules.resident_search.evidence.revisions import revision_token
from app.modules.resident_search.evidence.utils import _topics_for_care_plan
from app.modules.resident_search.schemas import EvidenceCitation


def plan_row(**changes):
    return {
        "care_plan_id": uuid.uuid4(),
        "resident_id": uuid.uuid4(),
        "care_home_id": uuid.uuid4(),
        "floor_id": uuid.uuid4(),
        "domain": "mobility",
        "plan_goal": "Maintain safe transfers",
        "current_version": 2,
        "review_due": date(2026, 12, 1),
        "is_active": True,
        "plan_updated_at": datetime(2026, 10, 1, tzinfo=UTC),
        "version_id": uuid.uuid4(),
        "version_number": 2,
        "content": "Use a standing aid with two staff.\nCheck the equipment.",
        "version_created_at": datetime(2026, 9, 1, tzinfo=UTC),
        "change_reason": "Transfer support reviewed",
        **changes,
    }


def goal_row(plan_id, **changes):
    return {
        "id": uuid.uuid4(),
        "care_plan_id": plan_id,
        "goal_text": "Use wheelchair for longer distances",
        "baseline": "Assisted transfers",
        "target": "Maintain comfort",
        "measurement": "Daily review",
        "status": "in_progress",
        "set_at": datetime(2026, 9, 1, tzinfo=UTC),
        "review_date": date(2026, 12, 1),
        "achieved_date": None,
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 1, tzinfo=UTC),
        **changes,
    }


def result(rows):
    value = Mock()
    value.mappings.return_value.all.return_value = rows
    value.mappings.return_value.one_or_none.return_value = rows[0] if rows else None
    return value


async def test_find_and_get_return_the_same_complete_document():
    plan = plan_row()
    goal = goal_row(plan["care_plan_id"], status="achieved")
    session = Mock(execute=AsyncMock(side_effect=[result([plan]), result([goal])] * 2))
    adapter = CarePlanEvidenceAdapter(session)

    documents = await adapter.find(resident_id=plan["resident_id"], from_date=None, to_date=None, limit=10)
    reopened = await adapter.get(resident_id=plan["resident_id"], source_id=plan["care_plan_id"])

    assert documents == [reopened]
    assert reopened.source_type is EvidenceSourceType.CARE_PLAN
    assert reopened.authority_level is AuthorityLevel.CARE_PLAN
    assert reopened.evidence_id == f"care_plan:{plan['care_plan_id']}"
    assert reopened.status == "active"
    assert reopened.occurred_at == plan["version_created_at"]
    assert reopened.time_precision == "timestamp"
    assert reopened.effective_from is None and reopened.effective_to is None
    assert reopened.source_version.startswith("sha256:")
    assert {"mobility", "transfer", "staffing"} <= reopened.topic_tags
    assert "Use a standing aid with two staff. Check the equipment." in reopened.searchable_text
    assert "Care goal status: achieved." in reopened.searchable_text
    assert "Care goal: Use wheelchair for longer distances." in reopened.searchable_text
    assert reopened.structured_metadata["goals"] == [goal]
    assert reopened.structured_metadata["version_number"] == 2
    assert reopened.resident_id == plan["resident_id"]
    assert reopened.care_home_id == plan["care_home_id"]
    assert reopened.floor_id == plan["floor_id"]

    # Catch missing SQL bindings and accidental list/source query mix-ups.
    for statement, parameters in (call.args for call in session.execute.await_args_list):
        compiled = statement.params(**parameters).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"render_postcompile": True},
        )
        assert "..." not in str(compiled)
        assert compiled.params and all(value is not None for value in compiled.params.values())
    get_sql, get_params = session.execute.await_args_list[2].args
    assert "cp.id = :source_id" in str(get_sql)
    assert get_params == {"resident_id": plan["resident_id"], "source_id": plan["care_plan_id"]}


async def test_topic_filter_finds_a_match_after_the_first_page():
    unrelated = plan_row(domain="communication", content="Use picture cards")
    wanted = plan_row(domain="personal", content="Offer support")
    goal = goal_row(wanted["care_plan_id"], goal_text="Use standing aid")
    session = Mock(
        execute=AsyncMock(
            side_effect=[
                result([unrelated]),
                result([]),
                result([wanted]),
                result([goal]),
            ]
        )
    )
    documents = await CarePlanEvidenceAdapter(session).find(
        resident_id=wanted["resident_id"],
        from_date=None,
        to_date=None,
        topics={" TRANSFER "},
        limit=1,
    )
    assert [document.source_id for document in documents] == [wanted["care_plan_id"]]
    assert session.execute.await_args_list[2].args[1]["offset"] == 1


@pytest.mark.parametrize("current_only", [True, False])
async def test_recent_date_filters_do_not_hide_an_older_current_plan(current_only):
    plan = plan_row()
    session = Mock(execute=AsyncMock(side_effect=[result([plan]), result([])]))
    documents = await CarePlanEvidenceAdapter(session).find(
        resident_id=plan["resident_id"],
        from_date=datetime(2026, 11, 1, tzinfo=UTC),
        to_date=datetime(2026, 12, 1, tzinfo=UTC),
        current_only=current_only,
        limit=10,
    )
    assert len(documents) == 1
    assert documents[0].effective_from is None


@pytest.mark.parametrize("filters", [{"topics": set()}, {"topics": {"  "}}, {"statuses": set()}])
async def test_empty_filters_return_no_records_without_querying(filters):
    session = Mock(execute=AsyncMock())
    assert (
        await CarePlanEvidenceAdapter(session).find(
            resident_id=uuid.uuid4(),
            from_date=None,
            to_date=None,
            limit=10,
            **filters,
        )
        == []
    )
    session.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "filters, message",
    [
        ({"limit": 0}, "limit"),
        ({"limit": 501}, "limit"),
        ({"statuses": {"inactive"}}, "active"),
        ({"from_date": datetime(2026, 1, 1)}, "timezone-aware"),
        ({"to_date": datetime(2026, 1, 1)}, "timezone-aware"),
        ({"from_date": datetime(2026, 2, 1, tzinfo=UTC), "to_date": datetime(2026, 1, 1, tzinfo=UTC)}, "earlier"),
    ],
)
async def test_invalid_filters_fail_before_querying(filters, message):
    session = Mock(execute=AsyncMock())
    arguments = {"resident_id": uuid.uuid4(), "from_date": None, "to_date": None, "limit": 10, **filters}
    with pytest.raises(ValueError, match=message):
        await CarePlanEvidenceAdapter(session).find(**arguments)
    session.execute.assert_not_awaited()


async def test_missing_plan_and_nonmatching_topics_return_no_evidence():
    plan = plan_row()
    session = Mock(execute=AsyncMock(side_effect=[result([]), result([]), result([plan]), result([])]))
    adapter = CarePlanEvidenceAdapter(session)
    assert await adapter.find(resident_id=plan["resident_id"], from_date=None, to_date=None, limit=10) == []
    assert await adapter.get(resident_id=plan["resident_id"], source_id=plan["care_plan_id"]) is None
    assert (
        await adapter.find(
            resident_id=plan["resident_id"],
            from_date=None,
            to_date=None,
            limit=10,
            topics={"sleep"},
        )
        == []
    )


def test_revision_is_stable_and_detects_parent_version_and_goal_changes():
    plan = plan_row()
    goals = [goal_row(plan["care_plan_id"]), goal_row(plan["care_plan_id"])]
    document = CarePlanEvidenceAdapter._document(plan=plan, goals=goals)
    assert document.source_version == CarePlanEvidenceAdapter._document(plan=plan, goals=goals[::-1]).source_version
    mutations = [
        (plan | {"content": "Revised instructions"}, goals),
        (plan | {"review_due": date(2027, 1, 1)}, goals),
        (plan | {"current_version": 3, "version_number": 3}, goals),
        (plan, [goals[0] | {"status": "achieved"}, goals[1]]),
        (plan, [goals[0] | {"target": "Updated target"}, goals[1]]),
        (plan, goals[:1]),
        (plan, goals + [goal_row(plan["care_plan_id"])]),
    ]
    for changed_plan, changed_goals in mutations:
        assert (
            CarePlanEvidenceAdapter._document(
                plan=changed_plan,
                goals=changed_goals,
            ).source_version
            != document.source_version
        )


@pytest.mark.parametrize(
    "domain, expected",
    [
        ("behaviour_wellbeing", "wellbeing"),
        ("sleep", "sleep"),
        ("pain_management", "pain"),
        ("personal", "personal_care"),
    ],
)
def test_database_domains_have_topic_tags(domain, expected):
    assert expected in _topics_for_care_plan(domain, "", [])


def test_keyword_matching_is_case_insensitive_and_uses_word_boundaries():
    assert "transfer" in _topics_for_care_plan("unknown", "Standing AID", [])
    assert "transfer" not in _topics_for_care_plan("unknown", "hoisting", [])


def test_citations_accept_hashes_and_normalise_legacy_timestamp_revisions():
    plan = plan_row()
    document = CarePlanEvidenceAdapter._document(plan=plan, goals=[])
    fields = document.model_dump(
        include={
            "evidence_id",
            "source_type",
            "source_id",
            "source_version",
            "occurred_at",
            "title",
        }
    )
    citation = EvidenceCitation(**fields)
    assert EvidenceCitation.model_validate_json(citation.model_dump_json()) == citation
    local_time = datetime(2026, 9, 1, 1, tzinfo=timezone(timedelta(hours=1)))
    legacy = EvidenceCitation(**(fields | {"source_version": local_time}))
    assert legacy.source_version == "2026-09-01T00:00:00.000000+00:00"
    assert revision_token(local_time) == revision_token(local_time.astimezone(UTC))
    with pytest.raises(ValidationError, match="timezone-aware"):
        EvidenceCitation(**(fields | {"source_version": datetime(2026, 9, 1)}))
