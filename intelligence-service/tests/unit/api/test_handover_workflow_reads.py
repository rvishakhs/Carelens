import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from intelligence.api.handover import available_shifts
from intelligence.api.handover_review import read_draft, read_evidence
from tests.support.handover_review import database, fixture


def test_shift_choices_require_current_resident_permission():
    scope, job, _ = fixture()
    settings = SimpleNamespace(care_home_timezone="Europe/London")
    response = Response()
    shifts = asyncio.run(available_shifts(job.resident_id, response, scope, settings))
    assert len(shifts) == 4 and shifts[0].end <= datetime.now(UTC)
    assert response.headers["cache-control"] == "no-store"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(available_shifts(uuid4(), response, scope, settings))
    assert exc.value.status_code == 404


def test_specific_draft_preserves_original_claim_references():
    scope, job, original = fixture()
    db, _ = database(job, original, original)
    result = asyncio.run(read_draft(job.id, Response(), scope, db))
    assert result.job_id == job.id
    assert result.original_sections[0].claims[0].text == "Recorded care"


@pytest.mark.parametrize("endpoint", [read_draft, read_evidence])
def test_missing_or_inaccessible_job_returns_not_found(endpoint):
    scope, job, _ = fixture()
    db, _ = database(None)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(job.id, Response(), scope, db))
    assert exc.value.status_code == 404


def test_evidence_history_and_incomplete_coverage_preserved():
    scope, job, original = fixture()
    manifest = SimpleNamespace(
        retrieved_at=original.created_at, evidence_cutoff=None, coverage_complete=False, sources=[]
    )
    db, session = database(job, original, original, manifest)
    session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: [original]))
    response = Response()
    result = asyncio.run(read_evidence(job.id, response, scope, db))
    assert result["coverage_complete"] is False
    assert result["evidence_cutoff"] is None
    assert result["versions"][0]["version"] == 1
    assert response.headers["cache-control"] == "no-store"
    assert "resident_id" in str(session.scalar.call_args_list[-1].args[0])
