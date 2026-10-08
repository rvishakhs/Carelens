import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from intelligence.core.contracts import ExecutionContext
from intelligence.handover.contracts import HandoverSubmissionRequest
from intelligence.workers import scheduling


def inputs():
    resident = uuid4()
    return ExecutionContext(
        tenant_id=uuid4(),
        service_identity="test",
        trigger="scheduled",
        authorised_resident_ids=frozenset({resident}),
        permissions=frozenset({"handover:generate", "handover:schedule"}),
    ), HandoverSubmissionRequest(
        resident_id=resident,
        shift_start=datetime(2020, 1, 1, 7, tzinfo=UTC),
        shift_end=datetime(2020, 1, 1, 19, tzinfo=UTC),
    )


@pytest.mark.parametrize("existing", [False, True])
def test_scheduled_submission_reuses_job_or_creates_outbox_via_repository(monkeypatch, existing):
    context, request = inputs()
    session = SimpleNamespace(execute=AsyncMock())

    @asynccontextmanager
    async def transaction():
        yield session

    session.begin = transaction
    db = SimpleNamespace(session=transaction)
    job = SimpleNamespace(id=uuid4())
    find = AsyncMock(return_value=job if existing else None)
    create = AsyncMock(return_value=job)
    monkeypatch.setattr(scheduling, "find_existing_handover", find)
    monkeypatch.setattr(scheduling, "create_handover_job", create)
    assert (
        asyncio.run(
            scheduling.submit_scheduled(db, context=context, request=request, timezone="Europe/London")
        )
        == job.id
    )
    assert create.await_count == (0 if existing else 1)
    assert "pg_advisory_xact_lock" in str(session.execute.call_args_list[1].args[0])


@pytest.mark.parametrize("change", ["permission", "resident", "manual"])
def test_scheduled_submission_denies_invalid_authority(change):
    context, request = inputs()
    updates = {
        "permission": {"permissions": frozenset({"handover:generate"})},
        "resident": {"authorised_resident_ids": frozenset()},
        "manual": {"trigger": "manual"},
    }[change]
    with pytest.raises(ValueError):
        asyncio.run(
            scheduling.submit_scheduled(
                None, context=context.model_copy(update=updates), request=request, timezone="Europe/London"
            )
        )


def test_disabled_sweep_never_opens_credentials_or_database(monkeypatch):
    monkeypatch.setattr(scheduling, "ScheduleSettings", lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(scheduling, "Settings", lambda: pytest.fail("Opened runtime settings"))
    asyncio.run(scheduling.run_schedule_sweep())
