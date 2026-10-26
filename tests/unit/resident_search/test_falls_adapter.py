import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.modules.resident_search.evidence.falls import FallsEvidenceAdapter
from app.modules.resident_search.evidence.models import EvidenceDocument


def fall_row():
    return {
        "id": uuid.uuid4(),
        "resident_id": uuid.uuid4(),
        "care_home_id": uuid.uuid4(),
        "floor_id": uuid.uuid4(),
        "occurred_at": datetime(2026, 10, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 10, 2, tzinfo=UTC),
        "deleted_at": None,
        "severity": "no_injury",
        "location": "Lounge",
        "witnessed": False,
        "injuries": None,
        "likely_cause": "Lost balance",
        "action_taken": "Nurse reviewed.\nObservations started.",
        "post_fall_observations_required": True,
        "family_informed": False,
    }


async def test_find_and_get_create_the_same_complete_canonical_document():
    row = fall_row()
    result = Mock()
    result.mappings.return_value.all.return_value = [row]
    result.mappings.return_value.one_or_none.return_value = row
    session = Mock(execute=AsyncMock(return_value=result))
    adapter = FallsEvidenceAdapter(session)

    (document,) = await adapter.find(resident_id=row["resident_id"], from_date=None, to_date=None, limit=51)
    assert document == await adapter.get(resident_id=row["resident_id"], source_id=row["id"])
    assert document.evidence_id == f"fall:{row['id']}"
    assert document.resident_id == row["resident_id"]
    assert document.care_home_id == row["care_home_id"]
    assert document.floor_id == row["floor_id"]
    assert document.source_version == row["updated_at"]
    assert document.title == "Fall — no injury"
    assert "Nurse reviewed. Observations started." in document.searchable_text
    assert "Injuries: None" not in document.searchable_text
    assert document.structured_metadata["injuries"] is None
    assert document.structured_metadata["witnessed"] is False
    assert document.structured_metadata["post_fall_observations_required"] is True
    assert document.is_eligible and not document.is_deleted
    assert "recorded_by" not in document.structured_metadata


async def test_get_returns_none_when_source_is_not_visible():
    result = Mock()
    result.mappings.return_value.one_or_none.return_value = None
    adapter = FallsEvidenceAdapter(Mock(execute=AsyncMock(return_value=result)))
    assert await adapter.get(resident_id=uuid.uuid4(), source_id=uuid.uuid4()) is None


@pytest.mark.parametrize("limit", [0, -1, 501])
async def test_find_rejects_unbounded_limits(limit):
    session = Mock(execute=AsyncMock())
    with pytest.raises(ValueError, match="limit"):
        await FallsEvidenceAdapter(session).find(resident_id=uuid.uuid4(), from_date=None, to_date=None, limit=limit)
    session.execute.assert_not_awaited()


def test_document_rejects_a_citation_id_for_a_different_source():
    document = FallsEvidenceAdapter._document(fall_row())
    with pytest.raises(ValidationError, match="evidence_id"):
        EvidenceDocument.model_validate({**document.model_dump(), "evidence_id": f"fall:{uuid.uuid4()}"})
