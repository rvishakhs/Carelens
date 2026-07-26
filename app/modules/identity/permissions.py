"""The RBAC matrix: a single source of truth for role -> permission mapping.

This file *is* the RBAC test matrix's fixture (tests/rbac/ iterates it against every
endpoint x every role) and later gets pasted verbatim into the DPIA / DSPT evidence,
so keep it exhaustive rather than convenient.
"""

import enum
from collections.abc import Iterable

from fastapi import Depends

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
        }
    ),
    Role.FAMILY: frozenset(set()),  # Phase 5 -- consent machinery lands before any grant
    Role.EMERGENCY: frozenset({Permission.VIEW_RESIDENT, Permission.VIEW_MEDICATIONS}),  # Phase 3
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require(*permissions: Permission):
    """FastAPI dependency factory: `Depends(require(Permission.VIEW_HANDOVER))`.
    Requires ALL listed permissions."""

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        missing = [p for p in permissions if not role_has_permission(current_user.role, p)]
        if missing:
            raise PermissionDeniedError(f"missing permissions: {', '.join(m.value for m in missing)}")
        return current_user

    return _check


def all_permissions() -> Iterable[Permission]:
    return list(Permission)