"""FastAPI dependency chain: verify JWT -> resolve which care home the subject
belongs to -> sync local user -> resolve authorised floors. Every protected route
depends on get_current_user (directly or via permissions.require())."""

import uuid

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.floors.dependencies import get_floor_reader_for
from app.modules.identity.repository import UserRepository
from app.modules.identity.schemas import CurrentUser
from app.shared.database import bootstrap_session, rls_session
from app.shared.exceptions import PermissionDeniedError, UnauthenticatedError

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise UnauthenticatedError("missing bearer token")

    container = request.app.state.container
    claims = await container.token_verifier.verify(credentials.credentials)

    # care_home_id isn't on the token (see ports.py's TokenClaims docstring) -- look
    # it up first, via the one session allowed to read `users` without already
    # knowing the tenant. See bootstrap_session()'s docstring for why this can't just
    # be system_session().
    async with bootstrap_session() as session:
        care_home_id = await UserRepository(session).find_care_home_id_by_oidc_subject(claims.subject)
    if care_home_id is None:
        raise UnauthenticatedError("no CareLens account found for this identity; ask a manager to add you as staff")

    async with rls_session(care_home_id, claims.subject) as session:
        user = await UserRepository(session).sync_from_claims(claims)

        async with get_floor_reader_for(user.care_home_id, user.id) as floor_reader:
            floor_ids = await floor_reader.get_authorized_floor_ids(user.id)

        return CurrentUser(
            id=user.id,
            care_home_id=user.care_home_id,
            role=user.role,
            email=user.email,
            display_name=user.display_name,
            floor_ids=floor_ids,
        )


async def get_floor_scope(
    floor_id: uuid.UUID | None = Query(
        None,
        description="Restrict results to a single authorised floor; omit to see every floor you're authorised for.",
    ),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[uuid.UUID]:
    """Resolves the floor_ids to pass into rls_session() for a single request -- lets a
    user pick "just this floor" vs. "everything I'm authorised for"
    (current_user.floor_ids) per request/view, without changing what they're
    authorised for (that's still user_floor_links, granted/revoked via
    POST/DELETE /floors/access). Rejects a floor_id outside current_user.floor_ids
    rather than silently narrowing to an empty result, so a stale/wrong floor_id in
    the UI fails loudly instead of looking like "no residents on this floor"."""
    if floor_id is None:
        return current_user.floor_ids
    if floor_id not in current_user.floor_ids:
        raise PermissionDeniedError(f"not authorised for floor {floor_id}")
    return [floor_id]