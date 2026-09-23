"""Sequential PostgreSQL claim check; the harness rolls back all test rows.

Service transactions release savepoints inside an outer rollback transaction.
This test does not establish independent-worker concurrency behaviour.
"""

import asyncio
import os
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from intelligence.persistence.models import HandoverJob
from intelligence.workflow.resident_handover import reserve_handover_job
from tests.test_handover_submission import submission_harness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1",
        reason="Set INTELLIGENCE_RUN_DB_TESTS=1 to test local PostgreSQL",
    ),
]


def test_queued_handover_job_is_reserved_once() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            submitted = await h.submit()

            first = await reserve_handover_job(
                h.database,
                tenant_id=h.scope.tenant_id,
                job_id=submitted.job_id,
                lease_seconds=60,
            )

            assert first is not None
            assert first.job_id == submitted.job_id
            assert first.tenant_id == h.scope.tenant_id

            # A separate service transaction must not claim the running job.
            second = await reserve_handover_job(
                h.database,
                tenant_id=h.scope.tenant_id,
                job_id=submitted.job_id,
                lease_seconds=60,
            )
            assert second is None

            # Verify that the rejected second attempt changed nothing.
            async with h.database.session() as session:
                async with session.begin():
                    await session.execute(
                        text("SELECT set_config('intelligence.tenant_id', :tenant_id, true)"),
                        {"tenant_id": str(h.scope.tenant_id)},
                    )
                    job = await session.scalar(
                        select(HandoverJob).where(
                            HandoverJob.tenant_id == h.scope.tenant_id,
                            HandoverJob.id == submitted.job_id,
                        )
                    )
                    assert job is not None
                    assert job.state == "running"
                    assert job.attempts == 1
                    assert job.lease_token == first.lease_token
                    assert job.lease_expires_at == first.lease_expires_at
                    assert job.started_at is not None
                    assert job.heartbeat_at == job.started_at
                    assert job.lease_expires_at - job.started_at == timedelta(seconds=60)
                    assert job.completed_at is None
                    assert job.failure_code is None

    asyncio.run(exercise())
