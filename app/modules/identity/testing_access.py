"""Explicit, expiring development access for a single pilot staff account."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.modules.identity.schemas import CurrentUser


def allows_test_floor_management(settings: "Settings", user: "CurrentUser") -> bool:
    expires_at = settings.test_floor_manager_expires_at
    return (
        settings.environment == "development"
        and settings.test_floor_manager_user_id is not None
        and settings.test_floor_manager_tenant_id is not None
        and expires_at is not None
        and expires_at > datetime.now(UTC)
        and user.id == settings.test_floor_manager_user_id
        and user.care_home_id == settings.test_floor_manager_tenant_id
        and user.role == "nurse"
    )
