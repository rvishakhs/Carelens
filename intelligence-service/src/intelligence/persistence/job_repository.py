from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, cast
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update
from .models import DispatchOutbox, HandoverJob
from .models import HandoverJob

@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    tenant_id: UUID
    lease_token: UUID
    lease_expires_at: datetime

async def claim_handover_job(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    job_id: UUID,
    lease_seconds: int,
) -> ClaimedJob | None:

    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    statement = (
        select(HandoverJob)
        .where(
            HandoverJob.tenant_id == tenant_id,
            HandoverJob.id == job_id,
            HandoverJob.state == "queued",
            HandoverJob.next_attempt_at <= func.clock_timestamp(),
            HandoverJob.attempts < HandoverJob.max_attempts,
        )
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )

    row = await session.scalar(statement)

    if row is None:
        return None

    # Read the database clock after acquiring the lock.
    database_now: datetime = (
        await session.execute(select(func.clock_timestamp()))
    ).scalar_one()

    lease_token = uuid4()
    lease_expires_at = database_now + timedelta(seconds=lease_seconds)

    row.state = "running"
    row.lease_token = lease_token
    row.lease_expires_at = lease_expires_at
    row.heartbeat_at = database_now
    row.attempts += 1
    row.failure_code = None

    # Preserve when this job first started, including across retries.
    if row.started_at is None:
        row.started_at = database_now

    # Running jobs must not have a terminal completion timestamp.
    row.completed_at = None

    await session.flush()

    return ClaimedJob(
        job_id=row.id,
        tenant_id=row.tenant_id,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
    )

@dataclass(frozen=True)
class JobExecutionSnapshot:
    job_id: UUID
    tenant_id: UUID
    resident_id: UUID

    initiating_actor_id: UUID | None
    service_identity: str
    trigger: Literal["manual", "scheduled"]
    purpose: Literal["handover_generation"]

    shift_start: datetime
    shift_end: datetime
    timezone: str

async def load_claimed_job(
    session: AsyncSession,
    *,
    claim: ClaimedJob,
) -> JobExecutionSnapshot | None:
    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    statement = (
        select(HandoverJob)
        .where(
            HandoverJob.tenant_id == claim.tenant_id,
            HandoverJob.id == claim.job_id,
            HandoverJob.state == "running",
            HandoverJob.lease_token == claim.lease_token,
            HandoverJob.lease_expires_at > func.clock_timestamp(),
        )
        .execution_options(populate_existing=True)
    )

    job = await session.scalar(statement)

    if job is None:
        # Missing, inaccessible, no longer running, or lease lost.
        return None

    trigger = job.trigger_type

    if trigger not in ("manual", "scheduled"):
        raise ValueError("invalid_job_trigger")

    if job.purpose != "handover_generation":
        raise ValueError("invalid_job_purpose")

    if trigger == "manual" and job.requested_by is None:
        raise ValueError("manual_job_missing_actor")

    if trigger == "scheduled" and job.requested_by is not None:
        raise ValueError("scheduled_job_has_actor")

    validated_trigger = cast(Literal["manual", "scheduled"], trigger)

    return JobExecutionSnapshot(
        job_id=job.id,
        tenant_id=job.tenant_id,
        resident_id=job.resident_id,
        initiating_actor_id=job.requested_by,
        service_identity=job.service_identity,
        trigger=validated_trigger,
        purpose="handover_generation",
        shift_start=job.shift_start,
        shift_end=job.shift_end,
        timezone=job.timezone,
    )

async def renew_handover_lease(
    session: AsyncSession,
    *,
    claim: ClaimedJob,
    lease_seconds: int = 60,
) -> datetime | None:
    """Extend a currently owned, unexpired lease.

    Returns the new expiry, or None when ownership is no longer valid.
    The caller must commit the transaction before treating renewal as successful.
    """
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    statement = (
        update(HandoverJob)
        .where(
            HandoverJob.tenant_id == claim.tenant_id,
            HandoverJob.id == claim.job_id,
            HandoverJob.state == "running",
            HandoverJob.lease_token == claim.lease_token,
            HandoverJob.lease_expires_at > func.clock_timestamp(),
        )
        .values(
            heartbeat_at=func.clock_timestamp(),
            lease_expires_at=(
                func.clock_timestamp()
                + timedelta(seconds=lease_seconds)
            ),
        )
        .returning(HandoverJob.lease_expires_at)
        .execution_options(synchronize_session=False)
    )

    return await session.scalar(statement)


async def mark_handover_job_failed(
    session: AsyncSession,
    *,
    claim: ClaimedJob,
    failure_code: str,
) -> bool:
    """Fail a running job only while this worker owns its live lease."""
    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    allowed_codes = {
        "authorisation_denied",
        "gateway_rejected",
        "invalid_provider_output",
        "attempts_exhausted",
        "internal_error",
    }
    if failure_code not in allowed_codes:
        raise ValueError("Unsupported failure code")

    statement = (
        update(HandoverJob)
        .where(
            HandoverJob.tenant_id == claim.tenant_id,
            HandoverJob.id == claim.job_id,
            HandoverJob.state == "running",
            HandoverJob.lease_token == claim.lease_token,
            HandoverJob.lease_expires_at > func.clock_timestamp(),
        )
        .values(
            state="failed",
            failure_code=failure_code,
            completed_at=func.clock_timestamp(),
            lease_token=None,
            lease_expires_at=None,
        )
        .returning(HandoverJob.id)
        .execution_options(synchronize_session=False)
    )

    updated_id = (await session.execute(statement)).scalar_one_or_none()
    return updated_id is not None

async def retry_handover_job(
    session: AsyncSession,
    *,
    claim: ClaimedJob,
    failure_code: str,
    delay_seconds: int,
) -> Literal["queued", "failed", "not_owned"]:
    """Record a retry and its dispatch inside the caller's transaction."""
    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    if delay_seconds <= 0:
        raise ValueError("delay_seconds must be positive")

    allowed_codes = {
        "provider_unavailable",
        "provider_timeout",
        "connector_unavailable",
        "authorisation_unavailable",
    }
    if failure_code not in allowed_codes:
        raise ValueError("Unsupported retry failure code")

    # Serialize transitions for this job.
    row = await session.scalar(
        select(HandoverJob)
        .where(
            HandoverJob.tenant_id == claim.tenant_id,
            HandoverJob.id == claim.job_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if row is None:
        return "not_owned"

    # Check expiry after acquiring the lock.
    database_now = (
        await session.execute(select(func.clock_timestamp()))
    ).scalar_one()

    if (
        row.state != "running"
        or row.lease_token != claim.lease_token
        or row.lease_expires_at is None
        or row.lease_expires_at <= database_now
    ):
        return "not_owned"

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
            DispatchOutbox.tenant_id == claim.tenant_id,
            DispatchOutbox.job_id == claim.job_id,
        )
    )

    retry_at = database_now + timedelta(seconds=delay_seconds)

    row.state = "queued"
    row.failure_code = failure_code
    row.next_attempt_at = retry_at
    row.completed_at = None
    row.lease_token = None
    row.lease_expires_at = None

    session.add(
        DispatchOutbox(
            tenant_id=claim.tenant_id,
            job_id=claim.job_id,
            dispatch_number=(last_dispatch_number or 0) + 1,
            task_name="intelligence.handover.generate",
            state="pending",
            attempts=0,
            available_at=retry_at,
        )
    )

    await session.flush()
    return "queued"

