"""Run through scripts/test_outbox_concurrency.py against a disposable database."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from intelligence.core.contracts import Scope
from intelligence.handover.contracts import HandoverSubmissionRequest
from intelligence.persistence.database import Database
from intelligence.persistence.outbox_repository import claim_pending_dispatch
from tests.test_handover_submission import SubmissionHarness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTELLIGENCE_DISPOSABLE_TEST_URL") is None,
        reason="Use scripts/test_outbox_concurrency.py to provision a disposable database",
    ),
]


def test_competing_dispatchers_skip_locked_row() -> None:
    async def exercise() -> None:
        url = os.environ["INTELLIGENCE_DISPOSABLE_TEST_URL"]
        assert (make_url(url).database or "").startswith("intelligence_test_")
        database = Database(url)
        resident = uuid4()
        scope = Scope(
            tenant_id=uuid4(), actor_id=uuid4(),
            resident_ids=frozenset({resident}),
            permissions=frozenset({"handover:generate"}),
        )
        try:
            job_ids = set()
            for day in (1, 2):
                request = HandoverSubmissionRequest(
                    resident_id=resident,
                    shift_start=datetime(2020, 1, day, 7, tzinfo=UTC),
                    shift_end=datetime(2020, 1, day, 19, tzinfo=UTC),
                )
                result = await SubmissionHarness(database, scope, request).submit(key=f"shift-{day}")
                job_ids.add(result.job_id)

            async with database.session() as first, database.session() as second:
                async with first.begin(), second.begin():
                    for session in (first, second):
                        assert await session.scalar(text("SELECT current_user")) == "intelligence_app"
                        await session.execute(
                            text("SELECT set_config('intelligence.tenant_id', :tenant, true)"),
                            {"tenant": str(scope.tenant_id)},
                        )
                        await session.execute(text("SET LOCAL statement_timeout = '2000ms'"))
                    assert await first.scalar(text("SELECT pg_backend_pid()")) != await second.scalar(
                        text("SELECT pg_backend_pid()")
                    )
                    # A retains its row lock while B executes its claim.
                    claim_a = await claim_pending_dispatch(first, tenant_id=scope.tenant_id, lease_seconds=60)
                    claim_b = await claim_pending_dispatch(
                        second, tenant_id=scope.tenant_id, lease_seconds=60,
                    )
                    assert claim_a is not None and claim_b is not None
                    assert claim_a.outbox_id != claim_b.outbox_id
                    assert {claim_a.job_id, claim_b.job_id} == job_ids
                    assert await claim_pending_dispatch(
                        second, tenant_id=scope.tenant_id, lease_seconds=60,
                    ) is None
        finally:
            await database.close()

    asyncio.run(exercise())
