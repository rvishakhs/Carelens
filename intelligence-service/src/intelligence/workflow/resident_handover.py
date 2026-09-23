from uuid import UUID

from sqlalchemy import text

from intelligence.config import DatabaseSettings
from intelligence.persistence.database import Database
from intelligence.persistence.job_repository import (
    ClaimedJob,
    claim_handover_job,
    JobExecutionSnapshot,
    load_claimed_job,
)

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



async def run_resident_handover_workflow(
    *,
    tenant_id: UUID,
    job_id: UUID,
) -> ClaimedJob | None:
    settings = DatabaseSettings()

    db = Database(
        database_url = settings.database_url.get_secret_value(),
    )

    try:
        claim = await reserve_handover_job(
            db= db,
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
) -> tuple[ClaimedJob, JobExecutionSnapshot] | None:
    settings = DatabaseSettings()
    db = Database(
        database_url=settings.database_url.get_secret_value(),
    )

    try:
        return await prepare_handover_execution(
            db,
            tenant_id=tenant_id,
            job_id=job_id,
        )
    finally:
        await db.close()