# All Import statements
import asyncio
import logging
from uuid import UUID
from datetime import UTC, datetime
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from intelligence.agents.handover import HandoverAgent
from intelligence.connectors.carelens import CareLensClient
from intelligence.config import DatabaseSettings
from intelligence.core.contracts import Period
from intelligence.gateway.privacy import ReviewedTextPolicy
from intelligence.handover.authorization import ExecutionAuthorizer
from intelligence.handover.retrieval import retrieve_shift_observations
from intelligence.handover.contracts import HandoverRetrieval, HandoverAgentInput, GenerationMetadata
from intelligence.handover.metrics import calculate_handover_metrics
from intelligence.persistence.database import Database
from intelligence.persistence.draft_repository import save_original_and_complete_job
from intelligence.workflow.failure_handling import classify_failure, record_execution_failure

from intelligence.core.errors import HandoverLeaseLost, HandoverLeaseUncertain
from intelligence.persistence.job_repository import (
    ClaimedJob,
    claim_handover_job,
    JobExecutionSnapshot,
    load_claimed_job,
    renew_handover_lease,
)




logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 15
RENEWAL_TIMEOUT_SECONDS = 10


async def reserve_handover_job(
        db: Database,
        *,
        tenant_id: UUID,
        job_id: UUID,
        lease_seconds: int,
) -> ClaimedJob | None:
    # tenant_id must come from trusted execution context.
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "SELECT set_config("
                    "'intelligence.tenant_id', :tenant_id, true)"
                ),
                {"tenant_id": str(tenant_id)},
            )

            claim = await claim_handover_job(
                session,
                tenant_id=tenant_id,
                job_id=job_id,
                lease_seconds=lease_seconds,
            )

        # Transaction committed successfully; row lock released.

    return claim

async def renew_execution_lease(
    db: Database,
    *,
    claim: ClaimedJob,
    lease_seconds: int = 60,
) -> datetime | None:
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "SELECT set_config("
                    "'intelligence.tenant_id', :tenant_id, true)"
                ),
                {"tenant_id": str(claim.tenant_id)},
            )

            expires_at = await renew_handover_lease(
                session,
                claim=claim,
                lease_seconds=lease_seconds,
            )

        # Renewal is successful only after the transaction commits.
        return expires_at

async def require_execution_lease(
    db: Database,
    *,
    claim: ClaimedJob,
) -> datetime:
    try:
        async with asyncio.timeout(RENEWAL_TIMEOUT_SECONDS):
            expires_at = await renew_execution_lease(
                db,
                claim=claim,
                lease_seconds=60,
            )
    except asyncio.CancelledError:
        raise
    except (TimeoutError, SQLAlchemyError, OSError):
        raise HandoverLeaseUncertain(
            "Could not confirm job ownership"
        ) from None

    if expires_at is None:
        raise HandoverLeaseLost("Job lease is no longer valid")

    return expires_at

async def run_reserve_handover(
        *,
        tenant_id: UUID,
        job_id: UUID,
) -> ClaimedJob | None:
    settings = DatabaseSettings()

    db = Database(
        database_url=settings.database_url.get_secret_value(),
    )

    try:
        claim = await reserve_handover_job(
            db=db,
            tenant_id=tenant_id,
            job_id=job_id,
            lease_seconds=60
        )

        if claim is None:
            # No eligible queued job was claimed.
            return None

        # Next step: recheck authority and continue generation.
        # Returning the claim here does NOT complete the job.
        return claim
    finally:
        await db.close()


async def load_job_for_execution(
        db: Database,
        *,
        claim: ClaimedJob,
) -> JobExecutionSnapshot | None:
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "SELECT set_config("
                    "'intelligence.tenant_id', :tenant_id, true)"
                ),
                {"tenant_id": str(claim.tenant_id)},
            )

            snapshot = await load_claimed_job(
                session,
                claim=claim,
            )

    return snapshot


async def prepare_handover_execution(
        db: Database,
        *,
        tenant_id: UUID,
        job_id: UUID,
) -> tuple[ClaimedJob, JobExecutionSnapshot] | None:
    claim = await reserve_handover_job(
        db,
        tenant_id=tenant_id,
        job_id=job_id,
        lease_seconds=60,
    )

    if claim is None:
        return None

    snapshot = await load_job_for_execution(db, claim=claim)

    if snapshot is None:
        # Ownership was lost, the lease expired, or the job changed.
        return None

    return claim, snapshot


async def run_resident_handover_workflow(
        *,
        tenant_id: UUID,
        job_id: UUID,
        authorizer: ExecutionAuthorizer,
        client: CareLensClient,
        access_token: SecretStr,
        handover_agent: HandoverAgent,
        generation_metadata: GenerationMetadata,
        reviewed_text_policy: ReviewedTextPolicy | None = None,
):
    """Generate a draft while renewing ownership; stop renewing before saving."""
    settings = DatabaseSettings()
    db = Database(
        database_url=settings.database_url.get_secret_value(),
    )

    claim: ClaimedJob | None = None
    try:

        claim = await reserve_handover_job(
            db,
            tenant_id=tenant_id,
            job_id=job_id,
            lease_seconds=60,
        )

        if claim is None:
            return None

        snapshot = await load_job_for_execution(db, claim=claim)

        if snapshot is None:
            raise HandoverLeaseLost("Job ownership is no longer valid")

        await require_execution_lease(db, claim=claim)

        stop_renewing = asyncio.Event()

        async def keep_lease_alive() -> None:
            while not stop_renewing.is_set():
                try:
                    await asyncio.wait_for(
                        stop_renewing.wait(),
                        HEARTBEAT_INTERVAL_SECONDS,
                    )
                    return
                except TimeoutError:
                    pass

                await require_execution_lease(db, claim=claim)

        # TaskGroup stops processing if renewal fails, and cleans up on cancellation.
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(keep_lease_alive())

            # 1. Recheck current permission and resident eligibility.
            execution_context = await authorizer.authorise(job=snapshot)

            # 2. Retrieve records for this resident and shift.
            retrieval = await retrieve_shift_observations(
                client=client,
                context=execution_context,
                resident_id=snapshot.resident_id,
                access_token=access_token,
                shift=Period(
                    start=snapshot.shift_start,
                    end=snapshot.shift_end,
                ),
                care_home_timezone=snapshot.timezone,
            )

            # 3. Validate resident scope, sources, coverage and timestamps.
            validated_retrieval = HandoverRetrieval(
                evidence=retrieval,
                retrieved_at=datetime.now(UTC),
                evidence_cutoff=None,
                coverage_complete=False,
                warnings=(
                    "Clinical observations and care events retrieved; complete handover coverage "
                    "and source snapshot consistency have not been established.",
                ),
            )

            # 4. Calculate values using trusted code.
            metrics = calculate_handover_metrics(
                validated_retrieval.evidence,
                retrieval_complete=validated_retrieval.coverage_complete,
            )

            # 5. Assemble the trusted internal agent input.
            agent_input = HandoverAgentInput(
                execution_context=execution_context,
                job_id=snapshot.job_id,
                resident_id=snapshot.resident_id,
                period=Period(
                    start=snapshot.shift_start,
                    end=snapshot.shift_end,
                ),
                care_home_timezone=snapshot.timezone,
                retrieval=validated_retrieval,
                metrics=metrics,
            )

            # 6. Gateway prepares input, calls the provider,
            #    validates output and resolves source references.
            content = await handover_agent.generate(
                input=agent_input,
                text_policy=reviewed_text_policy,
            )

            # 6.5 Adding generation Metadata
            completed_generation = generation_metadata.model_copy(
                update={"generated_at": datetime.now(UTC)},
            )

            stop_renewing.set()

        # The heartbeat has finished before the save clears the lease.
        await require_execution_lease(db, claim=claim)
        # 7. One transaction:
        #    verify lease → save manifest → save original draft
        #    → set job draft_ready.
        draft_id = await save_original_and_complete_job(
            db=db,
            claim=claim,
            snapshot=snapshot,
            retrieval=validated_retrieval,
            content=content,
            generation=completed_generation,
        )

        return {
            "job_id": str(job_id),
            "draft_id": str(draft_id),
            "state": "draft_ready",
        }
    except asyncio.CancelledError:
        # Preserve shutdown/cancellation. Recovery handles abandoned leases.
        raise

    except Exception as error:
        if claim is None:
            # No confirmed claim is available to update.
            raise RuntimeError("handover_claim_unconfirmed") from None

        decision = classify_failure(error)

        try:
            outcome = await record_execution_failure(
                db,
                claim=claim,
                decision=decision,
            )
        except Exception:
            # Do not log raw errors, responses or clinical content.
            logger.error("handover_failure_recording_unavailable")
            raise RuntimeError(
                "handover_failure_recording_unavailable"
            ) from None

        logger.warning(
            "handover_execution_failed code=%s outcome=%s",
            decision.code,
            outcome,
        )

        # The database/outbox owns retry scheduling.
        # Report this execution as unsuccessful without exposing raw errors.
        raise RuntimeError(
            f"handover_execution_{outcome}:{decision.code}"
        ) from None

    finally:
        await db.close()

