"""Opt-in PostgreSQL recovery tests; harness rolls back every test."""
import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import func, select, text, update
from intelligence.persistence.models import DispatchOutbox, HandoverJob
from intelligence.persistence.job_repository import mark_handover_job_failed, retry_handover_job, renew_handover_lease
from intelligence.persistence.recovery_repository import recover_one_expired_job, recover_one_queued_job
from intelligence.workflow.resident_handover import reserve_handover_job
from tests.support.database import submission_harness

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1", reason="Requires disposable PostgreSQL")]

@asynccontextmanager
async def scoped(h):
    async with h.database.session() as s, s.begin():
        await s.execute(text("SELECT set_config('intelligence.tenant_id', :t, true)"), {"t": str(h.scope.tenant_id)})
        yield s

async def rows(h):
    async with scoped(h) as s:
        job = await s.scalar(select(HandoverJob).where(HandoverJob.tenant_id == h.scope.tenant_id))
        dispatches = (await s.scalars(select(DispatchOutbox).where(DispatchOutbox.tenant_id == h.scope.tenant_id))).all()
        return job, dispatches

@pytest.mark.parametrize("mode", ["retry", "failed", "expired", "exhausted", "rollback"])
def test_running_transitions_and_fencing(mode):
    async def run():
        async with submission_harness() as h:
            submitted = await h.submit()
            claim = await reserve_handover_job(h.database, tenant_id=h.scope.tenant_id, job_id=submitted.job_id, lease_seconds=60)
            async with scoped(h) as s:
                assert not await mark_handover_job_failed(s, claim=replace(claim, lease_token=uuid4()), failure_code="internal_error")
                assert await recover_one_expired_job(s, tenant_id=h.scope.tenant_id) is None
                if mode in {"expired", "exhausted"}:
                    values = dict(lease_expires_at=func.clock_timestamp()-timedelta(seconds=1))
                    if mode == "exhausted":
                        values["attempts"] = HandoverJob.max_attempts
                    await s.execute(update(HandoverJob).where(HandoverJob.id == submitted.job_id).values(**values))
            try:
                async with scoped(h) as s:
                    if mode in {"expired", "exhausted"}:
                        assert await recover_one_expired_job(s, tenant_id=h.scope.tenant_id) == ("failed" if mode == "exhausted" else "queued")
                    elif mode == "failed":
                        assert await mark_handover_job_failed(s, claim=claim, failure_code="internal_error")
                    else:
                        assert await retry_handover_job(s, claim=claim, failure_code="provider_timeout", delay_seconds=30) == "queued"
                    if mode == "rollback":
                        raise ValueError("rollback")
            except ValueError:
                assert mode == "rollback"
            job, dispatches = await rows(h)
            if mode == "rollback":
                assert job.state == "running" and len(dispatches) == 1
                return
            assert job.state == ("failed" if mode in {"failed", "exhausted"} else "queued")
            assert job.lease_token is None and job.lease_expires_at is None
            assert (job.completed_at is not None) == (job.state == "failed")
            assert len(dispatches) == (2 if job.state == "queued" else 1)
            if job.state == "queued":
                assert max(dispatches, key=lambda d: d.dispatch_number).available_at == job.next_attempt_at
            async with scoped(h) as s:
                assert await renew_handover_lease(s, claim=claim) is None
                assert not await mark_handover_job_failed(s, claim=claim, failure_code="internal_error")
                assert await retry_handover_job(s, claim=claim, failure_code="provider_timeout", delay_seconds=30) == "not_owned"
                assert await recover_one_expired_job(s, tenant_id=h.scope.tenant_id) is None
    asyncio.run(run())

@pytest.mark.parametrize("mode", ["old", "recent", "pending", "publishing", "future", "other_tenant", "rollback"])
def test_queued_recovery_requires_stale_publication(mode):
    async def run():
        async with submission_harness() as h:
            submitted = await h.submit()
            async with scoped(h) as s:
                values = dict(state="published", published_at=func.clock_timestamp()-timedelta(minutes=10))
                if mode == "recent":
                    values["published_at"] = func.clock_timestamp()
                if mode == "pending":
                    values = dict(state="pending", published_at=None)
                if mode == "publishing":
                    values = dict(state="publishing", published_at=None, lease_token=uuid4(), lease_expires_at=func.clock_timestamp()-timedelta(seconds=1))
                await s.execute(update(DispatchOutbox).where(DispatchOutbox.job_id == submitted.job_id).values(**values))
                if mode == "future":
                    await s.execute(update(HandoverJob).where(HandoverJob.id == submitted.job_id).values(next_attempt_at=func.clock_timestamp()+timedelta(minutes=10)))
            try:
                async with scoped(h) as s:
                    result = await recover_one_queued_job(s, tenant_id=uuid4() if mode == "other_tenant" else h.scope.tenant_id)
                    assert result == ("queued" if mode in {"old", "rollback"} else None)
                    if mode == "rollback":
                        raise ValueError("rollback")
            except ValueError:
                assert mode == "rollback"
            job, dispatches = await rows(h)
            assert job.attempts == 0
            assert len(dispatches) == (2 if mode == "old" else 1)
            if mode == "old":
                async with scoped(h) as s:
                    assert await recover_one_queued_job(s, tenant_id=h.scope.tenant_id) is None
    asyncio.run(run())
