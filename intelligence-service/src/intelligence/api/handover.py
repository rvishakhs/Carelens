from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select, text

from intelligence.persistence.models import HandoverJob
from intelligence.api.dependencies import actor, get_database, get_settings
from intelligence.config import Settings
from intelligence.core.contracts import Scope
from intelligence.core.errors import (
    AccessDenied,
    IdempotencyConflict,
    SubmissionBusy,
)
from intelligence.handover.contracts import (
    HandoverSubmissionRequest,
    HandoverSubmissionResponse,
    HandoverStatusResponse
)
from intelligence.handover.service import submit_manual_handover
from intelligence.persistence.database import Database


router = APIRouter(prefix="/v1/handovers", tags=["handovers"])


@router.post(
    "",
    response_model=HandoverSubmissionResponse,
    status_code=202,
)
async def submit_handover(
    payload: HandoverSubmissionRequest,
    response: Response,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^\S+$",
        ),
    ],
    scope: Scope = Depends(actor),
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> HandoverSubmissionResponse:
    try:
        result = await submit_manual_handover(
            database,
            scope=scope,
            request=payload,
            idempotency_key=idempotency_key,
            care_home_timezone=settings.care_home_timezone,
            service_identity=settings.service_identity,
        )
    except AccessDenied:
        raise HTTPException(
            status_code=404,
            detail="Resource unavailable",
        ) from None
    except IdempotencyConflict:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key already belongs to a different request",
        ) from None
    except SubmissionBusy:
        raise HTTPException(
            status_code=503,
            detail="Submission is busy; retry with the same Idempotency-Key",
            headers={"Retry-After": "1"},
        ) from None

    response.headers["Location"] = result.status_url
    return result

@router.get(
    "/{job_id}",
    response_model=HandoverStatusResponse,
)
async def get_handover_status(
    job_id: UUID,
    response: Response,
    scope: Scope = Depends(actor),
    database: Database = Depends(get_database),
) -> HandoverStatusResponse:
    # Pilot policy: staff authorised to generate can inspect accessible jobs.
    if "handover:generate" not in scope.permissions:
        raise HTTPException(404, "Resource unavailable")

    async with database.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "SELECT set_config("
                    "'intelligence.tenant_id', :tenant_id, true)"
                ),
                {"tenant_id": str(scope.tenant_id)},
            )

            job = await session.scalar(
                select(HandoverJob).where(
                    HandoverJob.id == job_id,
                    HandoverJob.tenant_id == scope.tenant_id,
                    HandoverJob.resident_id.in_(scope.resident_ids),
                )
            )

            if job is None:
                raise HTTPException(404, "Resource unavailable")

            result = HandoverStatusResponse.model_validate(
                {
                    "job_id": job.id,
                    "resident_id": job.resident_id,
                    "state": job.state,
                    "shift_start": job.shift_start,
                    "shift_end": job.shift_end,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                }
            )

    response.headers["Cache-Control"] = "no-store"
    return result