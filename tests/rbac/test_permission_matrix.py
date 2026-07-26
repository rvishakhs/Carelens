"""The RBAC test matrix: for every endpoint x every role, assert allow/deny. This file
starts with structural checks on the matrix itself; the endpoint x role sweep below is
a TODO that needs a real Postgres instance (testcontainers) and a seeded user per role
to drive through the actual FastAPI app -- see migrations/README.md for the RLS setup
this depends on.

This file is meant to be pasted into the DPIA / DSPT evidence largely verbatim once
the endpoint sweep is filled in -- keep it exhaustive, not just illustrative.
"""

from app.modules.identity.models import Role
from app.modules.identity.permissions import ROLE_PERMISSIONS, Permission, role_has_permission


def test_every_role_has_a_matrix_entry():
    for role in Role:
        assert role in ROLE_PERMISSIONS, f"{role} has no entry in ROLE_PERMISSIONS"


def test_family_role_has_no_permissions_yet():
    # Phase 5 -- consent machinery lands before any grant to the family role.
    assert ROLE_PERMISSIONS[Role.FAMILY] == frozenset()


def test_manager_can_view_and_export_audit_log():
    assert role_has_permission(Role.MANAGER, Permission.VIEW_AUDIT_LOG)
    assert role_has_permission(Role.MANAGER, Permission.EXPORT_AUDIT_LOG)


def test_carer_cannot_view_audit_log():
    assert not role_has_permission(Role.CARER, Permission.VIEW_AUDIT_LOG)


def test_carer_cannot_manage_medications():
    assert not role_has_permission(Role.CARER, Permission.MANAGE_MEDICATIONS)


def test_nurse_can_manage_medications():
    assert role_has_permission(Role.NURSE, Permission.MANAGE_MEDICATIONS)


# TODO before Phase 1 is done: parametrize over every registered route x every Role,
# hitting the real app (real Postgres via testcontainers, one seeded user per role per
# care home) and asserting 2xx/403 matches ROLE_PERMISSIONS exactly. This is the test
# that proves the matrix above isn't just documentation.
