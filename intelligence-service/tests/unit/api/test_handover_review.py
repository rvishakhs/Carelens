import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError

from intelligence.api.handover_review import RevisionRequest, latest_handover, present, save_revision
from tests.support.handover_review import database, fixture


def test_overview_keeps_evidence_details_and_unchanged_save_is_noop():
    scope, job, original = fixture()
    original.sections = [{"category": "nutrition_hydration", "claims": [{
        "text": 'Clinical event time: 2026-10-07T19:14:12+01:00. Recorded content: {"status_completed":true,"meal_most_eaten":true}',
        "sources": [{"source_type": "care_events", "source_id": str(uuid4()), "version": "1"}],
    }]}]
    view = present(job, original, original)
    assert "The resident ate most of the recorded meal portions." == view.text
    assert "At 19:14" in view.original_text
    assert view.overview_notice is not None
    db, session = database(job, original, original)
    result = asyncio.run(save_revision(job.id, RevisionRequest(expected_version_id=original.id,
        text=view.text), Response(), scope, db))
    assert result.id == original.id
    session.add.assert_not_called()


def test_source_quality_concerns_stay_visible_in_main_overview():
    _, job, original = fixture()
    original.sections = [{"category": "nutrition_hydration", "claims": [{
        "text": 'Clinical event time: 2026-10-07T19:14:12+01:00. Recorded content: {"status_completed":true,"meal_most_eaten":true}',
        "sources": [{"source_type": "care_events", "source_id": str(uuid4()), "version": "1"}],
    }]}]
    original.warnings = [{"message": "source_marked_implausible"}]
    assert present(job, original, original).text.startswith("A source record is flagged as implausible")


def test_legacy_original_is_readable_without_rewriting_persisted_text_or_staff_edits():
    _, job, original = fixture()
    raw = 'Clinical event time: 2026-10-07T19:14:12+01:00. Recorded content: {"status_completed":true,"offered_ml":150,"estimated_consumed_ml":75,"amount_half":true}'
    original.sections = [{"category": "nutrition_hydration", "claims": [{"text": raw, "sources": []}]}]
    original.warnings = [{"message": "consumed_volume_estimated_from_options_not_measured"}]
    result = present(job, original, original)
    assert "Nutrition & hydration" in result.text and "estimated at 75 ml" in result.text
    assert "Recorded content" not in result.text
    assert "not measured" in result.text
    assert original.sections[0]["claims"][0]["text"] == raw
    assert result.original_sections[0].claims[0].text != raw
    assert result.warnings == ["Some fluid intake amounts are estimates from recorded choices, not measured intake."]
    revision = SimpleNamespace(**(vars(original) | {"version_kind": "staff_revision"}))
    assert present(job, revision, original).text == raw


def test_latest_returns_original_and_no_store():
    scope, job, original = fixture()
    db, session = database(job, original, original)
    response = Response()
    result = asyncio.run(latest_handover(job.resident_id, response, scope, db))
    assert result.text == "Care delivered\nRecorded care"
    assert result.original_text == result.text
    assert result.warnings == ["Partial coverage"]
    assert response.headers["cache-control"] == "no-store"
    assert session.execute.call_args.args[1]["tenant_id"] == str(scope.tenant_id)
    sql = str(session.scalar.call_args_list[0].args[0])
    assert "tenant_id" in sql and "resident_id" in sql and "draft_ready" not in sql  # bound parameter


def test_missing_draft_is_empty_not_an_error():
    scope, job, _ = fixture()
    db, _ = database(None)
    assert asyncio.run(latest_handover(job.resident_id, Response(), scope, db)) is None


@pytest.mark.parametrize("denial", ["permission", "resident"])
def test_access_denied_before_database(denial):
    scope, job, _ = fixture()
    scope = scope.model_copy(
        update={"permissions": frozenset()} if denial == "permission" else {"resident_ids": frozenset()}
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(latest_handover(job.resident_id, Response(), scope, None))
    assert exc.value.status_code == 404


def test_save_appends_attributed_revision_without_overwriting_original():
    scope, job, original = fixture()
    db, session = database(job, original, original)
    request = RevisionRequest(expected_version_id=original.id, text=" Staff correction ")
    result = asyncio.run(save_revision(job.id, request, Response(), scope, db))
    revision = session.add.call_args.args[0]
    assert revision.version_number == 2
    assert revision.previous_version_id == original.id
    assert revision.authored_by == scope.actor_id
    assert revision.version_kind == "staff_revision"
    assert revision.sections[0]["claims"][0]["sources"] == []
    assert result.text == "Staff correction"
    assert result.original_text == "Care delivered\nRecorded care"
    assert original.sections[0]["claims"][0]["text"] == "Recorded care"
    assert "FOR UPDATE" in str(session.scalar.call_args_list[0].args[0])


def test_stale_revision_is_conflict():
    scope, job, original = fixture()
    db, session = database(job, original, original)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            save_revision(
                job.id, RevisionRequest(expected_version_id=uuid4(), text="Edit"), Response(), scope, db
            )
        )
    assert exc.value.status_code == 409
    session.add.assert_not_called()


def test_noop_and_retry_do_not_duplicate_revision():
    scope, job, original = fixture()
    revision = SimpleNamespace(
        **(
            vars(original)
            | {
                "id": uuid4(),
                "previous_version_id": original.id,
                "version_number": 2,
                "version_kind": "staff_revision",
                "authored_by": scope.actor_id,
                "sections": [{"category": "staff_handover", "claims": [{"text": "Edit", "sources": []}]}],
            }
        )
    )
    for expected in [original.id, revision.id]:
        db, session = database(job, revision, original)
        result = asyncio.run(
            save_revision(
                job.id, RevisionRequest(expected_version_id=expected, text="Edit"), Response(), scope, db
            )
        )
        assert result.id == revision.id
        session.add.assert_not_called()


@pytest.mark.parametrize("value", [" ", "x" * 20001])
def test_invalid_revision_rejected(value):
    with pytest.raises(ValidationError):
        RevisionRequest(expected_version_id=uuid4(), text=value)
