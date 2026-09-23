from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, cast
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
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