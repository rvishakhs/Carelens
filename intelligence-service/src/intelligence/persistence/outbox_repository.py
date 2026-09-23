from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DispatchOutbox


@dataclass(frozen=True)
class ClaimedDispatch:
    outbox_id: UUID
    tenant_id: UUID
    job_id: UUID
    task_name: str
    lease_token: UUID
    lease_expires_at: datetime

async def claim_pending_dispatch(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    lease_seconds: int,
) -> ClaimedDispatch | None:
    """Reserve one due outbox entry inside the caller's transaction."""

    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    statement = (
        select(DispatchOutbox)
        .where(
            DispatchOutbox.tenant_id == tenant_id,
            DispatchOutbox.state == "pending",
            DispatchOutbox.available_at <= func.clock_timestamp(),
        )
        .order_by(
            DispatchOutbox.available_at,
            DispatchOutbox.id,
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    row = await session.scalar(statement)

    if row is None:
        return None

    # Read the database clock after acquiring the row lock.
    database_now: datetime = (
        await session.execute(select(func.clock_timestamp()))
    ).scalar_one()

    lease_token = uuid4()
    lease_expires_at = database_now + timedelta(seconds=lease_seconds)

    row.state = "publishing"
    row.lease_token = lease_token
    row.lease_expires_at = lease_expires_at
    row.attempts += 1
    row.failure_code = None

    await session.flush()

    return ClaimedDispatch(
        outbox_id=row.id,
        tenant_id=row.tenant_id,
        job_id=row.job_id,
        task_name=row.task_name,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
    )

