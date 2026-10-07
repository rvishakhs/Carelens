from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DispatchOutbox, HandoverJob


@dataclass(frozen=True)
class ClaimedDispatch:
    outbox_id: UUID
    tenant_id: UUID
    job_id: UUID
    task_name: str
    lease_token: UUID
    lease_expires_at: datetime
    attempts: int = 1


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
        .join(
            HandoverJob,
            and_(
                HandoverJob.tenant_id == DispatchOutbox.tenant_id,
                HandoverJob.id == DispatchOutbox.job_id,
            ),
        )
        .where(
            DispatchOutbox.tenant_id == tenant_id,
            or_(
                DispatchOutbox.state == "pending",
                and_(
                    DispatchOutbox.state == "publishing",
                    DispatchOutbox.lease_expires_at <= func.clock_timestamp(),
                ),
            ),
            DispatchOutbox.available_at <= func.clock_timestamp(),
            HandoverJob.next_attempt_at <= func.clock_timestamp(),
        )
        .order_by(
            DispatchOutbox.available_at,
            DispatchOutbox.id,
        )
        .limit(1)
        .with_for_update(skip_locked=True, of=DispatchOutbox)
        .execution_options(populate_existing=True)
    )

    row = await session.scalar(statement)

    if row is None:
        return None

    # Read the database clock after acquiring the row lock.
    database_now: datetime = (await session.execute(select(func.clock_timestamp()))).scalar_one()

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
        attempts=row.attempts,
    )


async def finish_dispatch(
    session: AsyncSession,
    *,
    claim: ClaimedDispatch,
    published: bool,
    retry_seconds: float = 0,
) -> bool:
    """Fence bookkeeping by the current lease. Ambiguous delivery is retried."""
    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")
    if not published and retry_seconds <= 0:
        raise ValueError("Retry delay must be positive")
    values = {
        "state": "published" if published else "pending",
        "lease_token": None,
        "lease_expires_at": None,
        "published_at": func.clock_timestamp() if published else None,
        "failure_code": None if published else "publish_unconfirmed",
    }
    if not published:
        values["available_at"] = func.clock_timestamp() + timedelta(seconds=retry_seconds)
    result = await session.scalar(
        update(DispatchOutbox)
        .where(
            DispatchOutbox.tenant_id == claim.tenant_id,
            DispatchOutbox.id == claim.outbox_id,
            DispatchOutbox.job_id == claim.job_id,
            DispatchOutbox.state == "publishing",
            DispatchOutbox.lease_token == claim.lease_token,
            DispatchOutbox.lease_expires_at > func.clock_timestamp(),
        )
        .values(**values)
        .returning(DispatchOutbox.id)
        .execution_options(synchronize_session=False)
    )
    return result is not None
