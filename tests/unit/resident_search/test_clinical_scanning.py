import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.observations.schemas import ObservationRead
from app.modules.resident_search.evidence import clinical_observations as clinical
from app.modules.resident_search.evidence.models import EvidenceSourceType
from app.modules.resident_search.schemas import ResidentSearchRequest
from app.modules.resident_search.service import ResidentSearchService
from app.shared.events import InMemoryEventBus


def setup_adapter(monkeypatch, rows, budget=6):
    monkeypatch.setattr(clinical, "PAGE_SIZE", 2)
    monkeypatch.setattr(clinical, "MAX_SCAN_ROWS", budget)
    resident, home, floor = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    records = [ObservationRead(
        id=uuid.uuid4(), resident_id=resident, type=kind, value=value,
        recorded_at=datetime(2026, 11, 1, tzinfo=UTC), recorded_by=None,
        is_implausible=flag,
    ) for kind, value, flag in rows]

    async def read(*args, offset=0, limit=100, **kwargs):
        return records[offset:offset + limit]

    adapter = clinical.ClinicalObservationEvidenceAdapter(Mock(), EvidenceSourceType.OBSERVATION)
    adapter._reader = Mock(list_clinical_evidence_for_resident=AsyncMock(side_effect=read))
    adapter._resident_scope = AsyncMock(return_value=(home, floor))
    return adapter, resident, home, floor


@pytest.mark.parametrize("excluded", [
    ("weight", {"kg": 900}, True),
    ("note", {"text": "Unrelated"}, False),
])
async def test_skips_excluded_page_and_finds_older_match(monkeypatch, excluded):
    adapter, resident, _, _ = setup_adapter(monkeypatch, [excluded, excluded, ("weight", {"kg": 70}, False)])
    result = await adapter.find(resident_id=resident, from_date=None, to_date=None, limit=2, topics={"weight"})
    assert len(result.documents) == 1
    assert result.scanned_count == 3
    assert result.source_exhausted and not result.scan_limit_reached
    assert [c.kwargs["offset"] for c in adapter._reader.list_clinical_evidence_for_resident.await_args_list] == [0, 2]
    assert adapter._resident_scope.await_count == 1


async def test_stops_when_enough_matches_found(monkeypatch):
    adapter, resident, _, _ = setup_adapter(monkeypatch, [("weight", {"kg": 70}, False)] * 5)
    result = await adapter.find(resident_id=resident, from_date=None, to_date=None, limit=1)
    assert len(result.documents) == 1
    assert not result.scan_limit_reached
    assert adapter._reader.list_clinical_evidence_for_resident.await_count == 1


@pytest.mark.parametrize("has_match", [False, True])
async def test_budget_produces_persisted_partial_response(monkeypatch, has_match):
    rows = [("weight", {"kg": 900}, True)] * 4
    if has_match:
        rows[0] = ("weight", {"kg": 70}, False)
    adapter, resident, home, floor = setup_adapter(monkeypatch, rows, budget=3)
    repository = Mock(get_resident_scope=AsyncMock(return_value=(home, floor)),
                      create_search=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
                      add_citations=AsyncMock())
    response = await ResidentSearchService(repository, InMemoryEventBus(), {
        EvidenceSourceType.OBSERVATION: adapter,
    }).search(home, uuid.uuid4(), resident, ResidentSearchRequest(
        question="Observations", source_types=[EvidenceSourceType.OBSERVATION],
    ))
    assert response.answer_status.value == "partial"
    assert any("scanning 3 records" in notice for notice in response.coverage_limitations)
    assert repository.create_search.await_args.kwargs["answer_status"] == "partial"
    assert len(response.citations) == int(has_match)
    if not has_match:
        assert "within the scanned records" in response.answer
    calls = adapter._reader.list_clinical_evidence_for_resident.await_args_list
    assert [(c.kwargs["offset"], c.kwargs["limit"]) for c in calls] == [(0, 2), (2, 1)]


async def test_exact_budget_boundary_is_conservatively_incomplete(monkeypatch):
    adapter, resident, _, _ = setup_adapter(monkeypatch, [("weight", {"kg": 900}, True)] * 2, budget=2)
    result = await adapter.find(resident_id=resident, from_date=None, to_date=None, limit=1)
    assert result.scan_limit_reached and not result.source_exhausted
