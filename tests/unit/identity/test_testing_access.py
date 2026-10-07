from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app import PermissionDeniedError
from app.modules.identity.permissions import Permission, require


@pytest.mark.parametrize(("variation", "permission", "allowed"), [
    ("matching", Permission.MANAGE_FLOORS, True),
    ("other_user", Permission.MANAGE_FLOORS, False),
    ("other_tenant", Permission.MANAGE_FLOORS, False),
    ("production", Permission.MANAGE_FLOORS, False),
    ("expired", Permission.MANAGE_FLOORS, False),
    ("unconfigured", Permission.MANAGE_FLOORS, False),
    ("wrong_role", Permission.MANAGE_FLOORS, False),
    ("matching", Permission.MANAGE_USERS, False),
])
async def test_temporary_grant_is_narrow(monkeypatch, variation, permission, allowed):
    user = SimpleNamespace(id=uuid4(), care_home_id=uuid4(), role="nurse")
    settings = SimpleNamespace(
        environment="development",
        test_floor_manager_user_id=user.id,
        test_floor_manager_tenant_id=user.care_home_id,
        test_floor_manager_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    if variation == "other_user":
        user.id = uuid4()
    elif variation == "other_tenant":
        user.care_home_id = uuid4()
    elif variation == "production":
        settings.environment = "production"
    elif variation == "expired":
        settings.test_floor_manager_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif variation == "unconfigured":
        settings.test_floor_manager_user_id = None
    elif variation == "wrong_role":
        user.role = "carer"
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    registry = SimpleNamespace(get_permissions_for_role=AsyncMock(return_value=frozenset()))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        container=SimpleNamespace(permission_registry=registry)
    )))
    check = require(permission)
    if allowed:
        assert await check(request, user) is user
    else:
        with pytest.raises(PermissionDeniedError):
            await check(request, user)
