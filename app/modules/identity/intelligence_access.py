from uuid import UUID

from sqlalchemy import select

from app.modules.floors.models import Floor, UserFloorLink
from app.modules.identity.models import PermissionDefinition, RolePermission, User
from app.modules.identity.schemas import IntelligenceScopeRead
from app.modules.identity.service_grants import IntelligenceServiceGrant
from app.modules.residents.models import Resident
from app.shared.database import rls_session


class IntelligenceAccessDenied(Exception):
    """The staff member cannot use this intelligence service."""


async def visible_residents(grant: IntelligenceServiceGrant, *, staff_id: UUID | None = None) -> list[UUID]:
    async with rls_session(grant.tenant_id, grant.subject, list(grant.floor_ids)) as session:
        query = (
            select(Resident.id)
            .join(Floor, Floor.id == Resident.floor_id)
            .where(
                Resident.care_home_id == grant.tenant_id,
                Resident.id.in_(grant.resident_ids),
                Resident.deleted_at.is_(None),
                Resident.floor_id.in_(grant.floor_ids),
                Floor.care_home_id == grant.tenant_id,
                Floor.is_active.is_(True),
                Floor.deleted_at.is_(None),
            )
        )
        if staff_id is not None:
            query = query.where(
                Resident.floor_id.in_(
                    select(UserFloorLink.floor_id).where(
                        UserFloorLink.care_home_id == grant.tenant_id,
                        UserFloorLink.user_id == staff_id,
                        UserFloorLink.revoked_at.is_(None),
                        UserFloorLink.deleted_at.is_(None),
                    )
                )
            )
        return list((await session.scalars(query)).all())

async def resolve_staff_intelligence_scope(
    *,
    actor_id: UUID,
    grant: IntelligenceServiceGrant,
) -> IntelligenceScopeRead:
    # Previously checked by service_scope(). Keep this requirement
    # inside the shared function too, for its future staff-facing caller.
    if "handover:generate" not in grant.permissions:
        raise IntelligenceAccessDenied()

    if actor_id not in grant.generating_staff_ids:
        raise IntelligenceAccessDenied()

    async with rls_session(grant.tenant_id, grant.subject) as session:
        staff = await session.scalar(
            select(User).where(
                User.id == actor_id,
                User.care_home_id == grant.tenant_id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )

        if staff is None:
            raise IntelligenceAccessDenied()

        # Resolve current permissions directly from the database.
        permissions = set(
            (
                await session.scalars(
                    select(PermissionDefinition.code)
                    .join(
                        RolePermission,
                        RolePermission.permission_id == PermissionDefinition.id,
                    )
                    .where(RolePermission.role == staff.role)
                )
            ).all()
        )

        required_permissions = {
            "view_handover",
            "view_resident",
            "view_observation",
        }

        if not required_permissions.issubset(permissions):
            raise IntelligenceAccessDenied()

    resident_ids = await visible_residents(
        grant,
        staff_id=actor_id,
    )

    return IntelligenceScopeRead(
        tenant_id=grant.tenant_id,
        actor_id=actor_id,
        resident_ids=resident_ids,
        permissions=["handover:generate"],
    )
