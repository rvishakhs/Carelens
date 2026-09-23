"""Insertion primitive; request replay and concurrent-generation handling are still pending."""

from datetime import datetime, UTC
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fastapi import HTTPException
from intelligence.core.contracts import ExecutionContext, Scope
from intelligence.core.errors import AccessDenied, SubmissionBusy
from .contracts import HandoverSubmissionRequest, HandoverSubmissionResponse
from .authorization import authorise_manual_handover
from .idempotency import submission_fingerprint
from .validation import validate_completed_shift
from intelligence.persistence.database import Database
from intelligence.persistence.models import DispatchOutbox, HandoverJob, IdempotencyRecord
from intelligence.persistence.repositories import create_handover_job, find_existing_handover, add_idempotency_record, find_replayed_handover
from intelligence.core.errors import InvalidShift


class SubmissionRequest(Protocol):
    @property
    def resident_id(self) -> UUID: ...
    @property
    def shift_start(self) -> datetime: ...
    @property
    def shift_end(self) -> datetime: ...
    @property
    def timezone(self) -> str: ...

# These match the existing PostgreSQL constraint names.
RETRYABLE_UNIQUE_CONSTRAINTS = {
    "pk_idempotency_records",
    "handover_jobs_tenant_id_resident_id_shift_start_shift_end_g_key",
}

async def submit_manual_handover(
    db: Database,
    *,
    scope: Scope,
    request: HandoverSubmissionRequest,
    idempotency_key: str,
    care_home_timezone: str,
    service_identity: str,
) -> HandoverSubmissionResponse:
    # These values must come from trusted authentication/configuration.
    context = authorise_manual_handover(
        scope,
        resident_id=request.resident_id,
        service_identity=service_identity,
    )

    try:
        validate_completed_shift(
            request,
            care_home_timezone=care_home_timezone,
            now=datetime.now(UTC),
        )
    except InvalidShift:
        raise HTTPException(
            status_code=422,
            detail="Select a completed 07:00–19:00 or 19:00–07:00 shift",
        ) from None

    if not idempotency_key.strip() or len(idempotency_key) > 128:
        raise ValueError(
            "Idempotency-Key must be nonblank and at most 128 characters"
        )

    fingerprint = submission_fingerprint(request)

    for attempt in range(3):
        try:
            async with db.session() as session:
                async with session.begin():
                    await session.execute(
                        text(
                            "SELECT set_config("
                            "'intelligence.tenant_id', :tenant_id, true)"
                        ),
                        {"tenant_id": str(context.tenant_id)},
                    )

                    job = await find_replayed_handover(
                        session,
                        tenant_id=context.tenant_id,
                        actor_id=scope.actor_id,
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                    )

                    if job is None:
                        job = await find_existing_handover(
                            session,
                            tenant_id=context.tenant_id,
                            resident_id=request.resident_id,
                            shift_start=request.shift_start,
                            shift_end=request.shift_end,
                        )

                        if job is None:
                            job = await create_handover_job(
                                session,
                                context=context,
                                request=request,
                                care_home_timezone=care_home_timezone,
                            )

                        await add_idempotency_record(
                            session,
                            tenant_id=context.tenant_id,
                            actor_id=scope.actor_id,
                            idempotency_key=idempotency_key,
                            fingerprint=fingerprint,
                            job_id=job.id,
                        )

                    response = HandoverSubmissionResponse.model_validate(
                        {
                            "job_id": job.id,
                            "state": job.state,
                            "status_url": f"/v1/handovers/{job.id}",
                        }
                    )

                # Exiting session.begin() successfully commits the transaction.

            return response

        except IntegrityError as exc:
            # The failed transaction has already been rolled back.
            sqlstate = getattr(exc.orig, "sqlstate", None)
            diagnostic = getattr(exc.orig, "diag", None)
            constraint = getattr(diagnostic, "constraint_name", None)

            if (
                sqlstate != "23505"
                or constraint not in RETRYABLE_UNIQUE_CONSTRAINTS
            ):
                raise

            if attempt == 2:
                raise SubmissionBusy from None

            # A concurrent request won. Retry the lookups in a fresh transaction.

    raise SubmissionBusy
