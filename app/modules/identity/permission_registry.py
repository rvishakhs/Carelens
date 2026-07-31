"""The runtime, DB-backed permission source `require()` actually reads from --
`permissions.ROLE_PERMISSIONS` is the seed *source*, this is the seed *destination*
plus a process-local cache on top, so a role's grants can be edited (role_permissions
table, or a future admin UI) without a code deploy.

One instance lives on the container (a process-lifetime singleton, like every other
port/adapter) and is shared across requests -- the cache is populated lazily on first
use and only re-read via an explicit reload(), not on a timer, so permission checks
never pay a DB round trip on the hot path.
"""

import asyncio
from collections import defaultdict

from sqlalchemy import select

from app.modules.identity.models import PermissionDefinition, Role, RolePermission
from app.modules.identity.permissions import Permission
from app.shared.database import system_session


class PermissionRegistry:
    def __init__(self) -> None:
        self._cache: dict[Role, frozenset[Permission]] | None = None
        self._lock = asyncio.Lock()

    async def get_permissions_for_role(self, role: Role) -> frozenset[Permission]:
        if self._cache is None:
            await self.reload()
        assert self._cache is not None
        return self._cache.get(role, frozenset())

    async def reload(self) -> None:
        """Re-reads role_permissions from the DB. Call after any admin change to the
        table (or on a schedule, once there's an admin UI for it) -- until then,
        changes made directly in the DB won't be picked up by a running process until
        this runs or the process restarts."""
        async with self._lock:
            self._cache = await self._load()

    async def _load(self) -> dict[Role, frozenset[Permission]]:
        # permissions/role_permissions are system-wide reference data with no RLS
        # (migrations/versions/0018) -- a plain unscoped session is correct here, the
        # same way it would be for care_categories or ai_prompt_versions.
        async with system_session() as session:
            result = await session.execute(
                select(RolePermission.role, PermissionDefinition.code).join(
                    PermissionDefinition, RolePermission.permission_id == PermissionDefinition.id
                )
            )
            mapping: dict[Role, set[Permission]] = defaultdict(set)
            for role, code in result.all():
                mapping[role].add(Permission(code))
            return {role: frozenset(codes) for role, codes in mapping.items()}
