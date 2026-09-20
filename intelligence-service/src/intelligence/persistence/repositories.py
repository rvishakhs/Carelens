from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intelligence.core.errors import IdempotencyConflict
from intelligence.core.contracts import ExecutionContext
from intelligence.handover.contracts import HandoverSubmissionRequest
from .models import HandoverJob, IdempotencyRecord, DispatchOutbox

async def find_replayed_handover(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    fingerprint: str,
) -> HandoverJob | None:
    record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.actor_id == actor_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )

    if record is None:
        return None

    if record.request_fingerprint != fingerprint:
        raise IdempotencyConflict

    job = await session.scalar(
        select(HandoverJob).where(
            HandoverJob.tenant_id == tenant_id,
            HandoverJob.id == record.job_id,
        )
    )

    if job is None:
        raise RuntimeError("Idempotency mapping references an unavailable job")

    return job


async def find_existing_handover(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    resident_id: UUID,
    shift_start: datetime,
    shift_end: datetime,
    generation_number: int = 1,
) -> HandoverJob | None:
    return await session.scalar(
        select(HandoverJob).where(
            HandoverJob.tenant_id == tenant_id,
            HandoverJob.resident_id == resident_id,
            HandoverJob.shift_start == shift_start,
            HandoverJob.shift_end == shift_end,
            HandoverJob.generation_number == generation_number,
        )
    )

async def add_idempotency_record(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    fingerprint: str,
    job_id: UUID,
) -> None:
    record = IdempotencyRecord(
        tenant_id=tenant_id,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        job_id=job_id,
    )

    session.add(record)
    await session.flush()

async def create_handover_job(
        session: AsyncSession,
        *,
        context: ExecutionContext,
        request: HandoverSubmissionRequest,
        care_home_timezone: str,
) -> HandoverJob:
    job_id = uuid4()

    job = HandoverJob(
        id=job_id,
        tenant_id=context.tenant_id,
        resident_id=request.resident_id,
        requested_by=context.initiating_actor_id,
        trigger_type=context.trigger,
        service_identity=context.service_identity,
        purpose=context.purpose,
        timezone=care_home_timezone,
        shift_start=request.shift_start,
        shift_end=request.shift_end,
        generation_number=1,
        idempotency_key=f"job:{job_id}",
    )

    session.add(job)

    # Insert the parent job before its outbox record.
    await session.flush()

    session.add(
        DispatchOutbox(
            tenant_id=context.tenant_id,
            job_id=job.id,
        )
    )

    await session.flush()

    return job