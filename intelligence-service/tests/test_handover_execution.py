import asyncio
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import text

from intelligence.workflow.resident_handover import (
    load_job_for_execution,
    prepare_handover_execution,
    reserve_handover_job,
)
from tests.test_handover_submission import submission_harness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1",
        reason="Set INTELLIGENCE_RUN_DB_TESTS=1 to test local PostgreSQL",
    ),
]


def test_prepare_claims_and_loads_snapshot() -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            submitted = await h.submit()

            prepared = await prepare_handover_execution(
                h.database,
                tenant_id=h.scope.tenant_id,
                job_id=submitted.job_id,
            )

            assert prepared is not None
            claim, snapshot = prepared

            assert snapshot.job_id == claim.job_id == submitted.job_id
            assert snapshot.tenant_id == h.scope.tenant_id
            assert snapshot.resident_id == h.request.resident_id
            assert snapshot.initiating_actor_id == h.scope.actor_id
            assert snapshot.service_identity == "submission-integration-test"
            assert snapshot.trigger == "manual"
            assert snapshot.purpose == "handover_generation"
            assert snapshot.shift_start == h.request.shift_start
            assert snapshot.shift_end == h.request.shift_end
            assert snapshot.timezone == "Europe/London"

            # A duplicate delivery cannot claim this running job again.
            duplicate = await prepare_handover_execution(
                h.database,
                tenant_id=h.scope.tenant_id,
                job_id=submitted.job_id,
            )
            assert duplicate is None

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "scenario",
    ["wrong_token", "wrong_tenant", "expired", "cancelled"],
)


def test_loader_rejects_invalid_ownership(scenario: str) -> None:
    async def exercise() -> None:
        async with submission_harness() as h:
            submitted = await h.submit()
            claim = await reserve_handover_job(
                h.database,
                tenant_id=h.scope.tenant_id,
                job_id=submitted.job_id,
                lease_seconds=60,
            )
            assert claim is not None

            if scenario == "wrong_token":
                claim = replace(claim, lease_token=uuid4())

            elif scenario == "wrong_tenant":
                claim = replace(claim, tenant_id=uuid4())

            else:
                async with h.database.session() as session:
                    async with session.begin():
                        await session.execute(
                            text(
                                "SELECT set_config("
                                "'intelligence.tenant_id', :tenant_id, true)"
                            ),
                            {"tenant_id": str(h.scope.tenant_id)},
                        )

                        if scenario == "expired":
                            statement = text(
                                """
                                UPDATE handover_jobs
                                SET lease_expires_at =
                                    clock_timestamp() - interval '1 second'
                                WHERE tenant_id = :tenant_id
                                  AND id = :job_id
                                """
                            )
                        else:
                            # Respect the terminal-state and lease constraints.
                            statement = text(
                                """
                                UPDATE handover_jobs
                                SET state = 'cancelled',
                                    completed_at = clock_timestamp(),
                                    lease_token = NULL,
                                    lease_expires_at = NULL
                                WHERE tenant_id = :tenant_id
                                  AND id = :job_id
                                """
                            )

                        await session.execute(
                            statement,
                            {
                                "tenant_id": h.scope.tenant_id,
                                "job_id": submitted.job_id,
                            },
                        )

            snapshot = await load_job_for_execution(
                h.database,
                claim=claim,
            )
            assert snapshot is None

    asyncio.run(exercise())