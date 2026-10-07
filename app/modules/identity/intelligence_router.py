"""Service-only, read-only authority and clinical-feed interface.

Never creates a staff user or passes a service token through staff authentication.
All resident reads retain tenant/floor RLS plus explicit pilot resident scope.
"""

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from pydantic import AwareDatetime
from sqlalchemy import select

from app.config import get_settings
from app.modules.identity.models import CareHome, PermissionDefinition, RolePermission, User
from app.modules.identity.schemas import IntelligenceScopeRead
from app.modules.identity.service_grants import IntelligenceServiceGrant
from app.modules.observations.repository import ObservationRepository
from app.modules.observations.schemas import ObservationRead
from app.modules.residents.models import Resident, ResidentStatus
from app.shared.database import rls_session

from app.modules.identity.intelligence_access import (
    IntelligenceAccessDenied,
    resolve_staff_intelligence_scope,
    visible_residents,
)




router = APIRouter(prefix="/internal/intelligence", tags=["intelligence-integration"])
bearer = HTTPBearer(auto_error=False)


async def service_scope(
    tenant_id: UUID,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> IntelligenceServiceGrant:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    candidates = [g for g in settings.intelligence_service_grants if g.tenant_id == tenant_id]
    if credentials is None or not candidates:
        raise HTTPException(403, "Service access denied")
    issuer = settings.oidc_issuer.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            jwks = await client.get(f"{issuer}/protocol/openid-connect/certs")
        if jwks.status_code != 200:
            raise HTTPException(503, "Identity provider unavailable")
        keys = jwks.json()
        if not isinstance(keys, dict) or not isinstance(keys.get("keys"), list):
            raise HTTPException(503, "Identity provider unavailable")
    except (httpx.RequestError, ValueError):
        raise HTTPException(503, "Identity provider unavailable") from None
    try:
        claims = jwt.decode(
            credentials.credentials,
            keys,
            algorithms=["RS256"],
            issuer=issuer,
            audience=settings.intelligence_service_audience,
            options={"require_exp": True, "require_sub": True, "require_aud": True},
        )
    except jwt.JWTError:
        raise HTTPException(401, "Invalid service token") from None
    matching = [g for g in candidates if str(g.subject) == claims.get("sub") and g.client_id == claims.get("azp")]
    if len(matching) != 1 or "handover:generate" not in matching[0].permissions:
        raise HTTPException(403, "Service access denied")
    grant = matching[0]
    async with rls_session(grant.tenant_id, grant.subject) as session:
        home = await session.scalar(
            select(CareHome.id).where(
                CareHome.id == grant.tenant_id,
                CareHome.deleted_at.is_(None),
            )
        )
    if home is None:
        raise HTTPException(403, "Service access denied")
    return grant




@router.get("/authority/service")
async def service_grant(grant: IntelligenceServiceGrant = Depends(service_scope)) -> dict:
    return {
        "tenant_id": grant.tenant_id,
        "service_identity": grant.service_identity,
        "resident_ids": await visible_residents(grant),
        "permissions": sorted(grant.permissions),
    }


async def is_eligible(grant: IntelligenceServiceGrant, resident_id: UUID) -> bool:
    if resident_id not in grant.eligible_resident_ids or resident_id not in await visible_residents(grant):
        return False
    async with rls_session(grant.tenant_id, grant.subject, list(grant.floor_ids)) as session:
        return (
            await session.scalar(
                select(Resident.id).where(
                    Resident.id == resident_id,
                    Resident.care_home_id == grant.tenant_id,
                    Resident.deleted_at.is_(None),
                    Resident.status == ResidentStatus.ACTIVE,
                    Resident.discharge_date.is_(None),
                )
            )
            is not None
        )


@router.get("/authority/residents/{resident_id}/eligibility")
async def resident_eligibility(
    resident_id: UUID,
    grant: IntelligenceServiceGrant = Depends(service_scope),
) -> dict:
    return {
        "tenant_id": grant.tenant_id,
        "resident_id": resident_id,
        "eligible": await is_eligible(grant, resident_id),
    }


@router.get("/observations", response_model=list[ObservationRead])
async def observations(
    resident_id: UUID,
    since: AwareDatetime,
    until: AwareDatetime,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    grant: IntelligenceServiceGrant = Depends(service_scope),
) -> list[ObservationRead]:
    if since >= until:
        raise HTTPException(422, "since must precede until")
    if not await is_eligible(grant, resident_id):
        raise HTTPException(403, "Resident execution access denied")
    async with rls_session(grant.tenant_id, grant.subject, list(grant.floor_ids)) as session:
        return await ObservationRepository(session).list_for_resident(
            resident_id,
            limit,
            offset=offset,
            since=since,
            until=until,
        )

@router.get(
    "/authority/staff/{actor_id}",
    response_model=IntelligenceScopeRead,
)
async def staff_grant(
    actor_id: UUID,
    grant: IntelligenceServiceGrant = Depends(service_scope),
) -> IntelligenceScopeRead:
    try:
        return await resolve_staff_intelligence_scope(
            actor_id=actor_id,
            grant=grant,
        )
    except IntelligenceAccessDenied:
        raise HTTPException(
            status_code=403,
            detail="Staff execution access denied",
        ) from None
