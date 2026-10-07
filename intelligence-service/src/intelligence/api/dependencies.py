from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from intelligence.config import Settings
from intelligence.core.contracts import Scope
from intelligence.persistence.database import Database
from intelligence.connectors.staff_identity import (
    StaffAccessDenied,
    StaffIdentityUnavailable,
    StaffUnauthenticated,
)

bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


async def actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Scope:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={
                "WWW-Authenticate": "Bearer",
                "Cache-Control": "no-store",
            },
        )

    reader = request.app.state.staff_identity_reader

    try:
        return await reader.resolve(credentials.credentials)

    except StaffUnauthenticated:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired credentials",
            headers={
                "WWW-Authenticate": "Bearer",
                "Cache-Control": "no-store",
            },
        ) from None

    except StaffAccessDenied:
        raise HTTPException(
            status_code=403,
            detail="Intelligence access denied",
            headers={"Cache-Control": "no-store"},
        ) from None

    except StaffIdentityUnavailable:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
            headers={"Cache-Control": "no-store"},
        ) from None

