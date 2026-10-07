from datetime import timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelligence.persistence.models import DispatchOutbox, HandoverJob


async def recover_one_expired_job(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    retry_delay_seconds: int = 30,
) -> Literal["queued", "failed"] | None:
    """Recover at most one expired job in the caller's transaction."""
    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    if retry_delay_seconds <= 0:
        raise ValueError("retry_delay_seconds must be positive")

    row = await session.scalar(
        select(HandoverJob)
        .where(
            HandoverJob.tenant_id == tenant_id,
            HandoverJob.state == "running",
            HandoverJob.lease_expires_at <= func.clock_timestamp(),
        )
        .order_by(HandoverJob.lease_expires_at, HandoverJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )

    if row is None:
        return None

    database_now = (
        await session.execute(select(func.clock_timestamp()))
    ).scalar_one()

    # Recheck ownership state after acquiring the lock.
    if (
        row.state != "running"
        or row.lease_expires_at is None
        or row.lease_expires_at > database_now
    ):
        return None

    if row.attempts >= row.max_attempts:
        row.state = "failed"
        row.failure_code = "attempts_exhausted"
        row.completed_at = database_now
        row.lease_token = None
        row.lease_expires_at = None

        await session.flush()
        return "failed"

    last_dispatch_number = await session.scalar(
        select(func.max(DispatchOutbox.dispatch_number))
        .where(
            DispatchOutbox.tenant_id == tenant_id,
            DispatchOutbox.job_id == row.id,
        )
    )

    retry_at = database_now + timedelta(seconds=retry_delay_seconds)

    row.state = "queued"
    row.failure_code = "lease_expired"
    row.next_attempt_at = retry_at
    row.completed_at = None
    row.lease_token = None
    row.lease_expires_at = None

    session.add(
        DispatchOutbox(
            tenant_id=tenant_id,
            job_id=row.id,
            dispatch_number=(last_dispatch_number or 0) + 1,
            task_name="intelligence.handover.generate",
            state="pending",
            attempts=0,
            available_at=retry_at,
        )
    )

    await session.flush()
    return "queued"

async def recover_one_queued_job(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    stale_seconds: int = 300,
) -> Literal["queued", "failed"] | None:
    """Redispatch a due job only after all its dispatches are old and published.

    Publication is not proof of consumption. Duplicate delivery is safe because
    execution claims the job under a lock. Pending/publishing entries are left
    to the dispatcher, including expired publication leases.
    """
    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")
    if stale_seconds <= 0:
        raise ValueError("stale_seconds must be positive")

    unpublished = select(DispatchOutbox.id).where(
        DispatchOutbox.tenant_id == HandoverJob.tenant_id,
        DispatchOutbox.job_id == HandoverJob.id,
        DispatchOutbox.state != "published",
    ).exists()
    latest_publication = select(func.max(DispatchOutbox.published_at)).where(
        DispatchOutbox.tenant_id == HandoverJob.tenant_id,
        DispatchOutbox.job_id == HandoverJob.id,
    ).scalar_subquery()
    row = await session.scalar(
        select(HandoverJob).where(
            HandoverJob.tenant_id == tenant_id,
            HandoverJob.state == "queued",
            HandoverJob.next_attempt_at <= func.clock_timestamp(),
            ~unpublished,
            latest_publication <= func.clock_timestamp() - timedelta(seconds=stale_seconds),
        ).order_by(HandoverJob.next_attempt_at, HandoverJob.id)
        .limit(1).with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    if row is None:
        return None

    # Read dispatch state again after locking the job. All redispatch writers
    # must hold this same parent lock.
    dispatches = (await session.scalars(select(DispatchOutbox).where(
        DispatchOutbox.tenant_id == tenant_id,
        DispatchOutbox.job_id == row.id,
    ).execution_options(populate_existing=True))).all()
    now = (await session.execute(select(func.clock_timestamp()))).scalar_one()
    if (
        row.state != "queued" or row.next_attempt_at > now
        or not dispatches
        or any(d.state != "published" or d.published_at is None for d in dispatches)
        or max(d.published_at for d in dispatches) > now - timedelta(seconds=stale_seconds)
    ):
        return None
    if row.attempts >= row.max_attempts:
        row.state = "failed"
        row.failure_code = "attempts_exhausted"
        row.completed_at = now
        await session.flush()
        return "failed"

    row.failure_code = "delivery_unconfirmed"
    row.next_attempt_at = now
    session.add(DispatchOutbox(
        tenant_id=tenant_id, job_id=row.id,
        dispatch_number=max(d.dispatch_number for d in dispatches) + 1,
        task_name="intelligence.handover.generate", state="pending",
        attempts=0, available_at=now,
    ))
    await session.flush()
    return "queued"
