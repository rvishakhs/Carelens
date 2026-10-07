import asyncio
import logging
from uuid import UUID
from sqlalchemy import text

from intelligence.config import DatabaseSettings, DispatcherSettings
from intelligence.persistence.database import Database
from intelligence.persistence.recovery_repository import recover_one_expired_job, recover_one_queued_job


async def recover_jobs(
    db: Database,
    *,
    tenant_id: UUID,
    batch_size: int = 50,
    queued: bool = False,
    stale_seconds: int = 300,
) -> dict[str, int]:
    if not 1 <= batch_size <= 500:
        raise ValueError("batch_size must be between 1 and 500")

    counts = {"queued": 0, "failed": 0}

    for _ in range(batch_size):
        async with db.session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "SELECT set_config("
                        "'intelligence.tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )

                if queued:
                    outcome = await recover_one_queued_job(
                        session, tenant_id=tenant_id, stale_seconds=stale_seconds,
                    )
                else:
                    outcome = await recover_one_expired_job(session, tenant_id=tenant_id)

        # Count only committed changes.
        if outcome is None:
            break

        counts[outcome] += 1

    return counts

async def run_recovery_sweep() -> None:

    logger = logging.getLogger(__name__)
    tenants = DispatcherSettings()
    db = Database(
        DatabaseSettings().database_url.get_secret_value()
    )

    try:
        for tenant_id in dict.fromkeys(tenants.tenant_ids):
            try:
                async with asyncio.timeout(30):
                    counts = await recover_jobs(
                        db,
                        tenant_id=tenant_id,
                        batch_size=50,
                    )

                async with asyncio.timeout(30):
                    queued_counts = await recover_jobs(
                        db, tenant_id=tenant_id, batch_size=50, queued=True,
                        stale_seconds=tenants.queued_recovery_seconds,
                    )
                for key in counts:
                    counts[key] += queued_counts[key]
                if counts["queued"] or counts["failed"]:
                    logger.info(
                        "handover_recovery queued=%s failed=%s",
                        counts["queued"],
                        counts["failed"],
                    )
            except Exception:
                # Continue with other tenants; never log raw DB errors.
                logger.error("handover_recovery_sweep_unavailable")
    finally:
        await db.close()