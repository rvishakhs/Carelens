"""The RBAC matrix: a single source of truth for role -> permission mapping.

This file *is* the RBAC test matrix's fixture (tests/rbac/ iterates it against every
endpoint x every role) and later gets pasted verbatim into the DPIA / DSPT evidence,
so keep it exhaustive rather than convenient.
"""

import enum
from collections.abc import Iterable

from fastapi import Depends, Request

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import Role
from app.modules.identity.schemas import CurrentUser
from app.shared.exceptions import PermissionDeniedError


class Permission(str, enum.Enum):
    VIEW_HANDOVER = "view_handover"
    VIEW_RESIDENT = "view_resident"
    CREATE_OBSERVATION = "create_observation"
    VIEW_OBSERVATION = "view_observation"
    VIEW_SUMMARY = "view_summary"
    SUBMIT_SUMMARY_FEEDBACK = "submit_summary_feedback"
    MANAGE_MEDICATIONS = "manage_medications"
    VIEW_MEDICATIONS = "view_medications"
    APPROVE_SUGGESTION = "approve_suggestion"  # Phase 2, matrix pre-seeded now
    VIEW_AUDIT_LOG = "view_audit_log"
    EXPORT_AUDIT_LOG = "export_audit_log"
    MANAGE_USERS = "manage_users"
    VIEW_FLOORS = "view_floors"
    MANAGE_FLOORS = "manage_floors"
    RECORD_CARE_EVENT = "record_care_event"
    MANAGE_CARE_TEMPLATES = "manage_care_templates"
    VIEW_AI_INSIGHTS = "view_ai_insights"
    MANAGE_AI_ALERTS = "manage_ai_alerts"


# This dict is the seed data for the DB-backed permissions/role_permissions tables
# (see app/modules/identity/permission_registry.py) -- it is no longer read directly
# at request time, but stays here as the single human-readable source the seed
# migration's data is generated from. Update this, then regenerate the seed.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CARER: frozenset(
        {
            Permission.VIEW_HANDOVER,
            Permission.VIEW_RESIDENT,
            Permission.CREATE_OBSERVATION,
            Permission.VIEW_OBSERVATION,
            Permission.VIEW_SUMMARY,
            Permission.SUBMIT_SUMMARY_FEEDBACK,
            Permission.VIEW_MEDICATIONS,
            Permission.VIEW_FLOORS,
            Permission.RECORD_CARE_EVENT,
        }
    ),
    Role.NURSE: frozenset(
        {
            Permission.VIEW_HANDOVER,
            Permission.VIEW_RESIDENT,
            Permission.CREATE_OBSERVATION,
            Permission.VIEW_OBSERVATION,
            Permission.VIEW_SUMMARY,
            Permission.SUBMIT_SUMMARY_FEEDBACK,
            Permission.MANAGE_MEDICATIONS,
            Permission.VIEW_MEDICATIONS,
            Permission.APPROVE_SUGGESTION,
            Permission.VIEW_FLOORS,
            Permission.RECORD_CARE_EVENT,
            Permission.VIEW_AI_INSIGHTS,
            Permission.MANAGE_AI_ALERTS,
        }
    ),
    Role.MANAGER: frozenset(
        {
            Permission.VIEW_HANDOVER,
            Permission.VIEW_RESIDENT,
            Permission.VIEW_OBSERVATION,
            Permission.VIEW_SUMMARY,
            Permission.VIEW_MEDICATIONS,
            Permission.VIEW_AUDIT_LOG,
            Permission.EXPORT_AUDIT_LOG,
            Permission.MANAGE_USERS,
            Permission.VIEW_FLOORS,
            Permission.MANAGE_FLOORS,
            Permission.MANAGE_CARE_TEMPLATES,
            Permission.VIEW_AI_INSIGHTS,
            Permission.MANAGE_AI_ALERTS,
        }
    ),
    # Per-home administrative staff: everything a manager has today. Kept as a
    # distinct role (rather than aliased to MANAGER) so the two can diverge later
    # without a data migration -- e.g. if "manager" becomes shift-scoped and "admin"
    # stays home-wide.
    Role.ADMIN: frozenset(
        {
            Permission.VIEW_HANDOVER,
            Permission.VIEW_RESIDENT,
            Permission.VIEW_OBSERVATION,
            Permission.VIEW_SUMMARY,
            Permission.VIEW_MEDICATIONS,
            Permission.VIEW_AUDIT_LOG,
            Permission.EXPORT_AUDIT_LOG,
            Permission.MANAGE_USERS,
            Permission.VIEW_FLOORS,
            Permission.MANAGE_FLOORS,
            Permission.MANAGE_CARE_TEMPLATES,
            Permission.VIEW_AI_INSIGHTS,
            Permission.MANAGE_AI_ALERTS,
        }
    ),
    # Multi-home oversight -- same grants as admin for now, everywhere; scoping
    # "every home" instead of "one home" is a Keycloak/claims concern (which homes a
    # headoffice token is issued for), not a different permission set.
    Role.HEADOFFICE: frozenset(
        {
            Permission.VIEW_HANDOVER,
            Permission.VIEW_RESIDENT,
            Permission.VIEW_OBSERVATION,
            Permission.VIEW_SUMMARY,
            Permission.VIEW_MEDICATIONS,
            Permission.VIEW_AUDIT_LOG,
            Permission.EXPORT_AUDIT_LOG,
            Permission.MANAGE_USERS,
            Permission.VIEW_FLOORS,
            Permission.MANAGE_FLOORS,
            Permission.MANAGE_CARE_TEMPLATES,
            Permission.VIEW_AI_INSIGHTS,
            Permission.MANAGE_AI_ALERTS,
        }
    ),
    # Platform operator, not care-home staff -- everything, including cross-cutting
    # config (care template management) that even a manager shouldn't casually touch.
    Role.SYSTEM_ADMIN: frozenset(set(Permission)),
    Role.FAMILY: frozenset(set()),  # Phase 5 -- consent machinery lands before any grant
    Role.EMERGENCY: frozenset({Permission.VIEW_RESIDENT, Permission.VIEW_MEDICATIONS}),  # Phase 3
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    """Reads the static ROLE_PERMISSIONS seed dict, not the DB -- for tests and the
    migration that seeds role_permissions from it. Request-time checks go through
    require() -> PermissionRegistry (DB-backed, editable without a deploy), not this
    function; see permission_registry.py's docstring for why the two are split."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require(*permissions: Permission):
    """FastAPI dependency factory: `Depends(require(Permission.VIEW_HANDOVER))`.
    Requires ALL listed permissions, checked against the DB-backed PermissionRegistry
    on request.app.state.container -- not the static ROLE_PERMISSIONS dict above."""

    async def _check(request: Request, current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        registry = request.app.state.container.permission_registry
        granted = await registry.get_permissions_for_role(current_user.role)
        missing = [p for p in permissions if p not in granted]
        if missing:
            raise PermissionDeniedError(f"missing permissions: {', '.join(m.value for m in missing)}")
        return current_user

    return _check


def all_permissions() -> Iterable[Permission]:
    return list(Permission)