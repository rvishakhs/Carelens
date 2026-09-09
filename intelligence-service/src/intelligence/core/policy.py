from uuid import UUID

from intelligence.core.contracts import Scope
from intelligence.core.errors import AccessDenied


def require_access(scope: Scope, resident_id: UUID, permission: str) -> None:
    if resident_id not in scope.resident_ids or permission not in scope.permissions:
        raise AccessDenied
