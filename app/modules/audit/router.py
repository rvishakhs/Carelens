import csv
import io
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditEventRead
from app.modules.audit.service import AuditService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.shared.database import rls_session

router = APIRouter(prefix="/audit", tags=["audit"])


async def get_audit_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[AuditRepository]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield AuditRepository(session)


@router.get("", response_model=list[AuditEventRead])
async def list_audit_events(
    entity_type: str | None = None,
    since: datetime | None = None,
    _: CurrentUser = Depends(require(Permission.VIEW_AUDIT_LOG)),
    repository: AuditRepository = Depends(get_audit_repository),
) -> list[AuditEventRead]:
    events = await repository.list_events(entity_type=entity_type, since=since)
    return [AuditEventRead.model_validate(e) for e in events]


@router.get("/export")
async def export_audit_events(
    current_user: CurrentUser = Depends(require(Permission.EXPORT_AUDIT_LOG)),
    repository: AuditRepository = Depends(get_audit_repository),
) -> StreamingResponse:
    """Exports are themselves audited -- the manager who pulled this CSV shows up in
    the very next row a subsequent export would return."""
    events = await repository.list_events(limit=10_000)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "created_at", "actor_user_id", "action", "entity_type", "entity_id", "justification"])
    for e in events:
        writer.writerow(
            [e.id, e.created_at.isoformat(), e.actor_user_id, e.action, e.entity_type, e.entity_id, e.justification]
        )
    buffer.seek(0)

    await AuditService(repository).log(
        care_home_id=current_user.care_home_id,
        actor_user_id=current_user.id,
        action="audit.exported",
        entity_type="audit_log",
    )

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )
