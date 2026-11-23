import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.observations.schemas import ObservationRead
from app.modules.resident_search.evidence.clinical_observations import ClinicalObservationEvidenceAdapter
from app.modules.resident_search.evidence.models import EvidenceSourceType


@pytest.mark.parametrize("kind,value,topic,expected", [
    ("fluid_intake", {"ml": 250}, "hydration", "Volume: 250 ml"),
    ("weight", {"kg": 70.5}, "weight", "Weight: 70.5 kg"),
    ("vitals", {"systolic_bp": 120, "diastolic_bp": 80, "spo2_pct": 98,
                "temperature_c": 36.5, "heart_rate_bpm": 72}, "vitals", "Systolic blood pressure: 120 mmHg"),
    ("meal", {"meal": "lunch", "fraction_eaten": 0}, "meal", "Fraction eaten (0–1): 0"),
    ("mobility", {"activity": "Transfer", "assistance_given": "Two staff"}, "transfer", "Assistance given: Two staff"),
    ("note", {"text": "Resident slept well"}, "observation", "Text: Resident slept well"),
])
async def test_native_find_and_get_preserve_typed_content(kind, value, topic, expected):
    row = ObservationRead(id=uuid.uuid4(), resident_id=uuid.uuid4(), type=kind,
                          value={**value, "unapproved_field": "DO NOT PROJECT"},
                          recorded_at=datetime(2026, 11, 1, tzinfo=UTC),
                          recorded_by=None, is_implausible=False)
    adapter = ClinicalObservationEvidenceAdapter(Mock(), EvidenceSourceType.OBSERVATION)
    adapter._resident_scope = AsyncMock(return_value=(uuid.uuid4(), uuid.uuid4()))
    adapter._reader = Mock(list_clinical_evidence_for_resident=AsyncMock(return_value=[row]))
    result = await adapter.find(resident_id=row.resident_id, from_date=None, to_date=None, limit=10)
    (document,) = result.documents
    assert document == await adapter.get(resident_id=row.resident_id, source_id=row.id)
    assert expected in document.searchable_text
    assert topic in document.topic_tags
    assert "DO NOT PROJECT" not in document.searchable_text
    assert "unapproved_field" not in document.structured_metadata["fields"]
    for key, recorded in value.items():
        assert document.structured_metadata["fields"][key] == recorded
    if kind == "note":
        assert document.topic_tags == {"observation"}


@pytest.mark.parametrize("group,types", [
    (EvidenceSourceType.NUTRITION, {"fluid_intake", "weight", "meal"}),
    (EvidenceSourceType.MOBILITY, {"mobility"}),
])
async def test_domain_find_and_reopen_request_native_types(group, types):
    adapter = ClinicalObservationEvidenceAdapter(Mock(), group)
    reader = AsyncMock(return_value=[])
    adapter._reader = Mock(list_clinical_evidence_for_resident=reader)
    resident_id = uuid.uuid4()
    await adapter.find(resident_id=resident_id, from_date=None, to_date=None, limit=10)
    await adapter.get(resident_id=resident_id, source_id=uuid.uuid4())
    assert all(call.kwargs["native_types"] == types for call in reader.await_args_list)


async def test_domain_query_filters_native_types_in_sql_before_limit():
    from sqlalchemy.dialects import postgresql
    from app.modules.observations.repository import ObservationRepository

    result = Mock()
    result.mappings.return_value.all.return_value = []
    session = Mock(execute=AsyncMock(return_value=result))
    await ObservationRepository(session).list_clinical_evidence_for_resident(
        uuid.uuid4(), source_types={"weight_records"}, native_types={"weight"}, limit=10, offset=100,
    )
    statement, params = session.execute.await_args.args
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "source_type = 'observations' AND type IN" in sql
    assert sql.index("AND type IN") < sql.index("LIMIT")
    assert params["native_types"] == ["weight"]
    assert params["source_types"] == ["weight_records"]
    assert params["offset"] == 100
    assert "ORDER BY recorded_at DESC, source_type, id" in sql


async def test_native_weight_retrieved_and_reopened_in_nutrition_domain():
    row = ObservationRead(id=uuid.uuid4(), resident_id=uuid.uuid4(), type="weight", value={"kg": 70},
                          recorded_at=datetime(2026, 11, 1, tzinfo=UTC), recorded_by=None, is_implausible=False)
    adapter = ClinicalObservationEvidenceAdapter(Mock(), EvidenceSourceType.NUTRITION)
    adapter._resident_scope = AsyncMock(return_value=(uuid.uuid4(), uuid.uuid4()))
    adapter._reader = Mock(list_clinical_evidence_for_resident=AsyncMock(return_value=[row]))
    result = await adapter.find(resident_id=row.resident_id, from_date=None, to_date=None,
                                   limit=10, topics={"weight"})
    (document,) = result.documents
    assert document == await adapter.get(resident_id=row.resident_id, source_id=row.id)
    assert "Weight: 70 kg" in document.searchable_text


async def test_overlapping_domains_only_cite_native_record_once():
    from types import SimpleNamespace
    from app.shared.events import InMemoryEventBus
    from app.modules.resident_search.service import ResidentSearchService
    from app.modules.resident_search.schemas import ResidentSearchRequest

    resident_id, home_id, floor_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    row = ObservationRead(id=uuid.uuid4(), resident_id=resident_id, type="weight", value={"kg": 70},
                          recorded_at=datetime(2026, 11, 1, tzinfo=UTC), recorded_by=None, is_implausible=False)
    adapters = {}
    for group in (EvidenceSourceType.OBSERVATION, EvidenceSourceType.NUTRITION):
        adapter = ClinicalObservationEvidenceAdapter(Mock(), group)
        adapter._resident_scope = AsyncMock(return_value=(home_id, floor_id))
        adapter._reader = Mock(list_clinical_evidence_for_resident=AsyncMock(return_value=[row]))
        adapters[group] = adapter
    repository = Mock(get_resident_scope=AsyncMock(return_value=(home_id, floor_id)),
                      create_search=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
                      add_citations=AsyncMock())
    response = await ResidentSearchService(repository, InMemoryEventBus(), adapters).search(
        home_id, uuid.uuid4(), resident_id,
        ResidentSearchRequest(question="Weight", source_types=list(adapters)),
    )
    assert len(response.citations) == 1
    assert response.citations[0].source_id == row.id
