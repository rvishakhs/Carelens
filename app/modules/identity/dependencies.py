"""FastAPI dependency chain: verify JWT -> load/sync local user -> resolve authorised
floors -> RLS-scoped session already used once here to persist the just-in-time user
record. Every protected route depends on get_current_user (directly or via
permissions.require())."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.floors.dependencies import get_floor_reader_for
from app.modules.identity.repository import UserRepository
from app.modules.identity.schemas import CurrentUser
from app.shared.database import rls_session
from app.shared.exceptions import UnauthenticatedError

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise UnauthenticatedError("missing bearer token")

    container = request.app.state.container
    claims = await container.token_verifier.verify(credentials.credentials)

    async with rls_session(claims.care_home_id, claims.subject) as session:
        user = await UserRepository(session).get_or_create_from_claims(claims)

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