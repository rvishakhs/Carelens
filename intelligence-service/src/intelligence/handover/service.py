from uuid import uuid4

from intelligence.persistence.models import (
    DispatchOutbox,
    HandoverJob,
    IdempotencyRecord,
)


async def insert_new_submission(
    db,
    context,
    request,
    idempotency_key: str,
    fingerprint: str,
):
    job_id = uuid4()

    async with db.session() as session:
        async with session.begin():
            job = HandoverJob(
                id=job_id,
                tenant_id=context.tenant_id,
                resident_id=request.resident_id,
                requested_by=context.actor_id,
                trigger="manual",
                shift_start=request.shift_start,
                shift_end=request.shift_end,
                generation_revision=1,
            )
            session.add(job)

            # Ensure the parent row exists before inserting its dependants.
            # flush() sends SQL; it does not commit.
            await session.flush()

            session.add_all([
                DispatchOutbox(
                    tenant_id=context.tenant_id,
                    job_id=job_id,
                ),
                IdempotencyRecord(
                    tenant_id=context.tenant_id,
                    actor_id=context.actor_id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    job_id=job_id,
                ),
            ])

        # Successful exit from session.begin() commits all three rows.

    return job_id