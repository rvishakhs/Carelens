"""Real PostgreSQL submission checks; an outer transaction rolls back every test.

Run with INTELLIGENCE_RUN_DB_TESTS=1. These are sequential integration tests,
not proof of the independent-connection concurrency/retry behaviour.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from intelligence.config import DatabaseSettings
from intelligence.core.contracts import Scope
from intelligence.core.errors import AccessDenied, IdempotencyConflict
from intelligence.handover.contracts import HandoverSubmissionRequest, HandoverSubmissionResponse
from intelligence.handover.service import submit_manual_handover
from intelligence.persistence.database import Database
from intelligence.persistence.models import DispatchOutbox, HandoverJob, IdempotencyRecord

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1",
        reason="Set INTELLIGENCE_RUN_DB_TESTS=1 to test local PostgreSQL",
    ),
]


@dataclass
class SubmissionHarness:
    database: Database
    scope: Scope
    request: HandoverSubmissionRequest

    async def submit(
        self,
        key: str = "first-request",
        *,
        scope: Scope | None = None,
        request: HandoverSubmissionRequest | None = None,
    ) -> HandoverSubmissionResponse:
        return await submit_manual_handover(
            self.database,
            scope=scope or self.scope,
            request=request or self.request,
            idempotency_key=key,
            care_home_timezone="Europe/London",
            service_identity="submission-integration-test",
        )

    async def counts(self) -> tuple[int, ...]:
        async with self.database.session() as session:
            async with session.begin():
                await session.execute(
                    text("SELECT set_config('intelligence.tenant_id', :tenant, true)"),
                    {"tenant": str(self.scope.tenant_id)},
                )
                counts = []
                for model in (HandoverJob, DispatchOutbox, IdempotencyRecord):
                    count = await session.scalar(
                        select(func.count()).select_from(model).where(model.tenant_id == self.scope.tenant_id)
                    )
                    counts.append(count)
                return tuple(counts)


@asynccontextmanager
async def submission_harness() -> AsyncIterator[SubmissionHarness]:
    settings = DatabaseSettings()
    database = Database(settings.database_url.get_secret_value())
    resident_id = uuid4()
    scope = Scope(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        resident_ids=frozenset({resident_id}),
        permissions=frozenset({"handover:generate"}),
    )
    request = HandoverSubmissionRequest(
        resident_id=resident_id,
        shift_start=datetime(2020, 1, 1, 7, tzinfo=UTC),
        shift_end=datetime(2020, 1, 1, 19, tzinfo=UTC),
    )
    try:
        async with database.engine.connect() as connection:
            outer_transaction = await connection.begin()
            try:
                role = await connection.scalar(text("SELECT current_user"))
                assert role == "intelligence_app", "Use runtime credentials, not migration credentials"
                # Service commits release savepoints, never the outer transaction.
                database.session_factory = async_sessionmaker(
                    bind=connection,
                    expire_on_commit=False,
                    autoflush=False,
                    join_transaction_mode="create_savepoint",
                )
                harness = SubmissionHarness(database, scope, request)
                yield harness
            finally:
                await outer_transaction.rollback()

            # Verify cleanup in a new transaction, with tenant context restored.
            async with connection.begin():
                await connection.execute(
                    text("SELECT set_config('intelligence.tenant_id', :tenant, true)"),
                    {"tenant": str(scope.tenant_id)},
                )
                for model in (HandoverJob, DispatchOutbox, IdempotencyRecord):
                    remaining = await connection.scalar(
                        select(func.count()).select_from(model).where(model.tenant_id == scope.tenant_id)
                    )
                    assert remaining == 0, f"Rollback left rows in {model.__tablename__}"
    finally:
        await database.close()


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
