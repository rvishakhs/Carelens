import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.resident_search.evidence.appointments import AppointmentsEvidenceAdapter
from app.modules.resident_search.evidence.models import EvidenceSourceType


def appointment_row() -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "resident_id": uuid.uuid4(),
        "care_home_id": uuid.uuid4(),
        "floor_id": uuid.uuid4(),
        "appointment_type": "hospital",
        "scheduled_at": datetime(2026, 10, 1, 10, tzinfo=UTC),
        "provider_name": "General Hospital",
        "location": "Outpatients",
        "reason": "Follow-up after fall.",
        "status": "completed",
        "outcome": "No fracture found.",
        "transport_required": True,
        "escort_required": True,
        "family_informed": False,
        "notes": "Return transport booked.",
        "updated_at": datetime(2026, 10, 2, tzinfo=UTC),
        "deleted_at": None,
    }


async def test_find_and_get_create_the_same_complete_appointment_document():
    row = appointment_row()
    result = Mock()
    result.mappings.return_value.all.return_value = [row]
    result.mappings.return_value.one_or_none.return_value = row
    adapter = AppointmentsEvidenceAdapter(Mock(execute=AsyncMock(return_value=result)))

    (document,) = await adapter.find(
        resident_id=row["resident_id"], from_date=None, to_date=None, limit=51
    )

    assert document == await adapter.get(resident_id=row["resident_id"], source_id=row["id"])
    assert document.evidence_id == f"appointment:{row['id']}"
    assert document.source_type is EvidenceSourceType.APPOINTMENT
    assert document.occurred_at == row["scheduled_at"]
    assert document.title == "Appointment — hospital"
    assert "Outcome: No fracture found." in document.searchable_text
    assert "Transport required: Yes." in document.searchable_text
    assert document.structured_metadata == {
        "appointment_type": "hospital",
        "scheduled_at": row["scheduled_at"],
        "provider_name": "General Hospital",
        "location": "Outpatients",
        "reason": "Follow-up after fall.",
        "status": "completed",
        "outcome": "No fracture found.",
        "transport_required": True,
        "escort_required": True,
        "family_informed": False,
        "notes": "Return transport booked.",
    }


@pytest.mark.parametrize("limit", [0, -1, 501])
async def test_find_rejects_invalid_limits_without_querying(limit: int):
    session = Mock(execute=AsyncMock())

    with pytest.raises(ValueError, match="limit"):
        await AppointmentsEvidenceAdapter(session).find(
            resident_id=uuid.uuid4(), from_date=None, to_date=None, limit=limit
        )

    session.execute.assert_not_awaited()


async def test_get_returns_none_when_the_appointment_is_not_visible():
    result = Mock()
    result.mappings.return_value.one_or_none.return_value = None
    adapter = AppointmentsEvidenceAdapter(Mock(execute=AsyncMock(return_value=result)))

    assert await adapter.get(resident_id=uuid.uuid4(), source_id=uuid.uuid4()) is None
