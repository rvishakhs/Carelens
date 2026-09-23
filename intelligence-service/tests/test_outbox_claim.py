import asyncio
import os

import pytest
from sqlalchemy import select, text
from uuid import uuid4

from intelligence.dispatcher.service import reserve_next_dispatch
from intelligence.persistence.models import DispatchOutbox, HandoverJob
from tests.test_handover_submission import submission_harness
from intelligence.persistence.outbox_repository import claim_pending_dispatch



pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1",
        reason="Set INTELLIGENCE_RUN_DB_TESTS=1 to test local PostgreSQL",
    ),
]


def test_pending_outbox_is_reserved_once() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            # 1. Create a synthetic job and its pending outbox entry.
            submitted = await h.submit()

            # 2. Reserve the pending entry.
            claim = await reserve_next_dispatch(
                h.database,
                tenant_id=h.scope.tenant_id,
            )

            assert claim is not None
            assert claim.job_id == submitted.job_id
            assert claim.tenant_id == h.scope.tenant_id
            assert claim.task_name == "intelligence.handover.generate"

            # 3. Read the saved state through a new session.
            async with h.database.session() as session:
                async with session.begin():
                    await session.execute(
                        text(
                            "SELECT set_config("
                            "'intelligence.tenant_id', :tenant_id, true)"
                        ),
                        {"tenant_id": str(h.scope.tenant_id)},
                    )

                    outbox = await session.scalar(
                        select(DispatchOutbox).where(
                            DispatchOutbox.tenant_id == h.scope.tenant_id,
                            DispatchOutbox.id == claim.outbox_id,
                        )
                    )

                    assert outbox is not None
                    assert outbox.state == "publishing"
                    assert outbox.attempts == 1
                    assert outbox.lease_token == claim.lease_token
                    assert outbox.lease_expires_at == claim.lease_expires_at
                    assert outbox.published_at is None
                    assert outbox.failure_code is None

                    job = await session.scalar(
                        select(HandoverJob).where(
                            HandoverJob.tenant_id == h.scope.tenant_id,
                            HandoverJob.id == submitted.job_id,
                        )
                    )

                    assert job is not None
                    assert job.state == "queued"

            # 4. This tenant has only one entry, now publishing.
            # It must not be selected again.
            second_claim = await reserve_next_dispatch(
                h.database,
                tenant_id=h.scope.tenant_id,
            )

            assert second_claim is None

    asyncio.run(exercise())

def test_rolled_back_claim_can_be_claimed_again() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            submitted = await h.submit()
            abandoned_token = None

            # Simulate failure after the row is updated,
            # but before the reservation transaction commits.
            with pytest.raises(
                RuntimeError,
                match="Simulated dispatcher failure",
            ):
                async with h.database.session() as session:
                    async with session.begin():
                        await session.execute(
                            text(
                                "SELECT set_config("
                                "'intelligence.tenant_id', :tenant_id, true)"
                            ),
                            {"tenant_id": str(h.scope.tenant_id)},
                        )

                        abandoned_claim = await claim_pending_dispatch(
                            session,
                            tenant_id=h.scope.tenant_id,
                            lease_seconds=60,
                        )

                        assert abandoned_claim is not None
                        abandoned_token = abandoned_claim.lease_token

                        raise RuntimeError("Simulated dispatcher failure")

            # The failed transaction rolled back.
            # Another reservation should now succeed.
            recovered_claim = await reserve_next_dispatch(
                h.database,
                tenant_id=h.scope.tenant_id,
            )

            assert recovered_claim is not None
            assert recovered_claim.job_id == submitted.job_id
            assert recovered_claim.lease_token != abandoned_token

            async with h.database.session() as session:
                async with session.begin():
                    await session.execute(
                        text(
                            "SELECT set_config("
                            "'intelligence.tenant_id', :tenant_id, true)"
                        ),
                        {"tenant_id": str(h.scope.tenant_id)},
                    )

                    outbox = await session.scalar(
                        select(DispatchOutbox).where(
                            DispatchOutbox.tenant_id == h.scope.tenant_id,
                            DispatchOutbox.id == recovered_claim.outbox_id,
                        )
                    )

                    assert outbox is not None
                    assert outbox.state == "publishing"

                    # The rolled-back increment did not persist.
                    assert outbox.attempts == 1

    asyncio.run(exercise())

def test_other_tenant_cannot_claim_outbox() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            submitted = await h.submit()
            other_tenant_id = uuid4()

            # Tenant B must not claim tenant A's pending entry.
            forbidden_claim = await reserve_next_dispatch(
                h.database,
                tenant_id=other_tenant_id,
            )

            assert forbidden_claim is None

            # Tenant A's entry must still be available.
            permitted_claim = await reserve_next_dispatch(
                h.database,
                tenant_id=h.scope.tenant_id,
            )

            assert permitted_claim is not None
            assert permitted_claim.job_id == submitted.job_id
            assert permitted_claim.tenant_id == h.scope.tenant_id

    asyncio.run(exercise())