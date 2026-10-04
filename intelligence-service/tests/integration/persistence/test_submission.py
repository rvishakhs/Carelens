"""Real PostgreSQL submission checks; an outer transaction rolls back every test.

Run with INTELLIGENCE_RUN_DB_TESTS=1. These are sequential integration tests,
not proof of the independent-connection concurrency/retry behaviour.
"""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from intelligence.core.errors import AccessDenied, IdempotencyConflict
from intelligence.persistence.models import DispatchOutbox
from tests.support.database import submission_harness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1",
        reason="Set INTELLIGENCE_RUN_DB_TESTS=1 to test local PostgreSQL",
    ),
]


def test_new_submission_creates_job_outbox_and_mapping() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            result = await h.submit()
            assert result.state == "queued"
            assert result.status_url == f"/v1/handovers/{result.job_id}"
            assert await h.counts() == (1, 1, 1)
            async with h.database.session() as session:
                async with session.begin():
                    await session.execute(
                        text("SELECT set_config('intelligence.tenant_id', :tenant, true)"),
                        {"tenant": str(h.scope.tenant_id)},
                    )
                    outbox = await session.scalar(
                        select(DispatchOutbox).where(DispatchOutbox.job_id == result.job_id)
                    )
                    assert outbox is not None
                    assert outbox.state == "pending"
                    assert outbox.published_at is None

    asyncio.run(exercise())


def test_same_key_and_request_replays_without_duplicate_rows() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            original = await h.submit()
            assert await h.submit() == original
            assert await h.counts() == (1, 1, 1)

    asyncio.run(exercise())


@pytest.mark.parametrize("change", ["resident", "shift"])
def test_same_key_with_changed_request_is_a_conflict(change: str) -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            await h.submit()
            if change == "resident":
                resident = uuid4()
                scope = h.scope.model_copy(update={"resident_ids": h.scope.resident_ids | {resident}})
                request = h.request.model_copy(update={"resident_id": resident})
            else:
                scope = h.scope
                request = h.request.model_copy(
                    update={
                        "shift_start": datetime(2020, 1, 2, 7, tzinfo=UTC),
                        "shift_end": datetime(2020, 1, 2, 19, tzinfo=UTC),
                    }
                )
            with pytest.raises(IdempotencyConflict):
                await h.submit(scope=scope, request=request)
            assert await h.counts() == (1, 1, 1)

    asyncio.run(exercise())


@pytest.mark.parametrize("different_actor", [False, True])
def test_independent_request_reuses_logical_job(different_actor: bool) -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            original = await h.submit()
            scope = h.scope.model_copy(update={"actor_id": uuid4()}) if different_actor else h.scope
            # Same key across actors is independent; same actor uses a new key.
            key = "first-request" if different_actor else "second-request"
            assert (await h.submit(key, scope=scope)).job_id == original.job_id
            assert await h.counts() == (1, 1, 2)

    asyncio.run(exercise())


def test_replay_rechecks_current_permission() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            await h.submit()
            revoked = h.scope.model_copy(update={"permissions": frozenset()})
            with pytest.raises(AccessDenied):
                await h.submit(scope=revoked)
            assert await h.counts() == (1, 1, 1)

    asyncio.run(exercise())


def test_mapping_failure_rolls_back_job_and_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_mapping(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Simulated mapping failure")

    monkeypatch.setattr("intelligence.handover.service.add_idempotency_record", fail_mapping)

    async def exercise() -> None:
        async with submission_harness() as h:
            with pytest.raises(RuntimeError, match="Simulated mapping failure"):
                await h.submit()
            assert await h.counts() == (0, 0, 0)

    asyncio.run(exercise())
