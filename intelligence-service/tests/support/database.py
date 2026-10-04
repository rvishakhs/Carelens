"""Real PostgreSQL submission checks; an outer transaction rolls back every test.

Run with INTELLIGENCE_RUN_DB_TESTS=1. These are sequential integration tests,
not proof of the independent-connection concurrency/retry behaviour.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from intelligence.config import DatabaseSettings
from intelligence.core.contracts import Scope
from intelligence.handover.contracts import HandoverSubmissionRequest, HandoverSubmissionResponse
from intelligence.handover.service import submit_manual_handover
from intelligence.persistence.database import Database
from intelligence.persistence.models import DispatchOutbox, HandoverJob, IdempotencyRecord


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
