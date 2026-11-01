import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.resident_search.evidence.careevent import CareEventEvidenceAdapter
from app.modules.resident_search.evidence.models import AuthorityLevel
from app.modules.resident_search.evidence.utils import _measurement_value, _topics_for_event


@pytest.fixture(autouse=True)
def postgres():
    """These unit tests use mocked sessions; no database container is needed."""


def event(**changes):
    row = dict(
        id=uuid.uuid4(),
        resident_id=uuid.uuid4(),
        care_home_id=uuid.uuid4(),
        floor_id=uuid.uuid4(),
        template_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        occurred_at=datetime(2026, 10, 1, tzinfo=UTC),
        updated_at=datetime(2026, 10, 2, tzinfo=UTC),
        deleted_at=None,
        status="completed",
        summary="Transfer completed.",
        note=" Staff assisted. ",
        category_name="Mobility",
        template_name="Standing hoist transfer",
    )
    return row | changes


def result(rows):
    value = Mock()
    value.mappings.return_value.all.return_value = rows
    value.mappings.return_value.one_or_none.return_value = rows[0] if rows else None
    return value


async def test_find_and_get_load_same_complete_document():
    row = event()
    options = [dict(care_event_id=row["id"], label="Two staff", note=None, created_at=row["updated_at"])]
    measurements = [
        dict(
            care_event_id=row["id"],
            name="Distance",
            unit="m",
            value_numeric=Decimal("0"),
            value_text=None,
            value_boolean=None,
            created_at=row["updated_at"],
        )
    ]
    session = Mock(execute=AsyncMock(side_effect=[result([row]), result(options), result(measurements)] * 2))
    adapter = CareEventEvidenceAdapter(session)
    docs = await adapter.find(resident_id=row["resident_id"], from_date=None, to_date=None, limit=10)
    reopened = await adapter.get(resident_id=row["resident_id"], source_id=row["id"])
    assert docs == [reopened]
    assert reopened.authority_level == AuthorityLevel.CARE_EVENT
    assert reopened.topic_tags == {"mobility", "transfer"}
    assert "Distance: 0 m." in reopened.searchable_text
    assert reopened.structured_metadata["note"] == "Staff assisted."
    sql, params = session.execute.call_args_list[0].args
    assert "ORDER BY" in str(sql) and "LIMIT" in str(sql)
    assert params["resident_id"] == row["resident_id"]
    get_sql, get_params = session.execute.call_args_list[3].args
    assert "e.id = :source_id" in str(get_sql) and "LIMIT" not in str(get_sql)
    assert get_params["source_id"] == row["id"]
    assert "r.deleted_at IS NULL" in str(sql)


async def test_topic_filter_searches_beyond_first_page():
    irrelevant = event(category_name="Nutrition", template_name="Breakfast")
    wanted = event()
    session = Mock(
        execute=AsyncMock(side_effect=[result([irrelevant] * 500), result([wanted]), result([]), result([])])
    )
    docs = await CareEventEvidenceAdapter(session).find(
        resident_id=wanted["resident_id"],
        from_date=None,
        to_date=None,
        limit=1,
        topics={"transfer"},
    )
    assert [doc.source_id for doc in docs] == [wanted["id"]]
    assert session.execute.call_args_list[1].args[1]["offset"] == 500


@pytest.mark.parametrize("current_only,expected", [(False, 2), (True, 1)])
async def test_history_preserves_refusals(current_only, expected):
    rows = [event(status="refused"), event()]
    session = Mock(execute=AsyncMock(side_effect=[result(rows), result([]), result([])]))
    docs = await CareEventEvidenceAdapter(session).find(
        resident_id=rows[0]["resident_id"],
        from_date=None,
        to_date=None,
        limit=10,
        current_only=current_only,
    )
    assert len(docs) == expected


@pytest.mark.parametrize(
    "filters", [dict(limit=0), dict(limit=501), dict(statuses={"unknown"}), dict(from_date=datetime(2026, 1, 1))]
)
async def test_bad_filters_do_not_query(filters):
    session = Mock(execute=AsyncMock())
    with pytest.raises(ValueError):
        await CareEventEvidenceAdapter(session).find(
            **(
                dict(
                    resident_id=uuid.uuid4(),
                    from_date=None,
                    to_date=None,
                    limit=10,
                )
                | filters
            )
        )
    session.execute.assert_not_awaited()


async def test_absent_source_does_not_load_children():
    session = Mock(execute=AsyncMock(return_value=result([])))
    adapter = CareEventEvidenceAdapter(session)
    assert await adapter.get(resident_id=uuid.uuid4(), source_id=uuid.uuid4()) is None
    assert session.execute.await_count == 1


def test_revision_detects_child_edits_deletion_and_template_changes():
    row = event()
    option = dict(label="Two staff", note=None, created_at=row["updated_at"])

    def revision(parent, children):
        return CareEventEvidenceAdapter._document(event=parent, options=children, measurements=[]).source_version

    original = revision(row, [option])
    assert original == revision(row, [option])
    assert original != revision(row, [option | {"label": "One staff"}])
    assert original != revision(row, [])
    assert original != revision(row | {"template_name": "Updated transfer"}, [option])


@pytest.mark.parametrize(
    "template,expected",
    [
        ("Fall", {"fall", "safety", "mobility"}),
        ("Sleeping", {"sleep"}),
        ("Meal", {"nutrition"}),
        ("Communication", {"communication"}),
        ("Bath", {"personal_care"}),
        ("Walking", {"mobility"}),
        ("Strip bedding", {"care_record"}),
    ],
)
def test_topics(template, expected):
    assert set(_topics_for_event("", template)) == expected


@pytest.mark.parametrize(
    "numeric,text,boolean,expected", [(0, None, None, "0"), (None, None, False, "No"), (None, "  ", None, None)]
)
def test_measurement_values(numeric, text, boolean, expected):
    assert (
        _measurement_value(dict(value_numeric=numeric, value_text=text, value_boolean=boolean, unit=None)) == expected
    )
