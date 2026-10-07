"""Independent connection recovery checks; disposable runner only."""
import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url

from intelligence.core.contracts import Scope
from intelligence.handover.contracts import HandoverSubmissionRequest
from intelligence.persistence.database import Database
from intelligence.persistence.models import DispatchOutbox, HandoverJob
from intelligence.persistence.recovery_repository import recover_one_expired_job, recover_one_queued_job
from intelligence.persistence.job_repository import renew_handover_lease
from intelligence.workflow.resident_handover import reserve_handover_job
from tests.support.database import SubmissionHarness

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    not os.environ.get("INTELLIGENCE_DISPOSABLE_TEST_URL"), reason="Requires disposable runner",
)]

@pytest.mark.parametrize("kind", ["expired", "queued"])
def test_competing_recovery_creates_one_dispatch(kind):
    async def run():
        url = os.environ["INTELLIGENCE_DISPOSABLE_TEST_URL"]
        assert (make_url(url).database or "").startswith("intelligence_test_")
        db = Database(url)
        resident = uuid4()
        scope = Scope(tenant_id=uuid4(), actor_id=uuid4(), resident_ids=frozenset({resident}), permissions=frozenset({"handover:generate"}))
        request = HandoverSubmissionRequest(resident_id=resident, shift_start=datetime(2020,1,1,7,tzinfo=UTC), shift_end=datetime(2020,1,1,19,tzinfo=UTC))
        async def context(s):
            assert await s.scalar(text("SELECT current_user")) == "intelligence_app"
            await s.execute(text("SELECT set_config('intelligence.tenant_id', :t, true)"), {"t": str(scope.tenant_id)})
            await s.execute(text("SET LOCAL statement_timeout = '2000ms'"))
        try:
            job = await SubmissionHarness(db, scope, request).submit()
            claim = None
            if kind == "expired":
                claim = await reserve_handover_job(db, tenant_id=scope.tenant_id, job_id=job.job_id, lease_seconds=60)
            async with db.session() as s, s.begin():
                await context(s)
                if claim:
                    await s.execute(update(HandoverJob).where(HandoverJob.id == job.job_id).values(lease_expires_at=func.clock_timestamp()-timedelta(seconds=1)))
                else:
                    await s.execute(update(DispatchOutbox).where(DispatchOutbox.job_id == job.job_id).values(state="published", published_at=func.clock_timestamp()-timedelta(minutes=10)))
            recover = recover_one_expired_job if claim else recover_one_queued_job
            async with db.session() as a, db.session() as b:
                async with a.begin(), b.begin():
                    await context(a)
                    await context(b)
                    assert await a.scalar(text("SELECT pg_backend_pid()")) != await b.scalar(text("SELECT pg_backend_pid()"))
                    assert await recover(a, tenant_id=scope.tenant_id) == "queued"
                    assert await recover(b, tenant_id=scope.tenant_id) is None
            async with db.session() as s, s.begin():
                await context(s)
                assert await recover(s, tenant_id=scope.tenant_id) is None
                assert await s.scalar(select(func.count()).select_from(DispatchOutbox).where(DispatchOutbox.job_id == job.job_id)) == 2
                if claim:
                    assert await renew_handover_lease(s, claim=claim) is None
        finally:
            await db.close()
    asyncio.run(run())
