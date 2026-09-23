from secrets import compare_digest

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from intelligence.config import Settings
from intelligence.connectors.synthetic import demo_scope
from intelligence.core.contracts import Scope
from intelligence.persistence.database import Database


bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


def actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> Scope:
    if credentials is None or not compare_digest(
        credentials.credentials.encode(),
        settings.demo_token.get_secret_value().encode(),
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid demo credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return demo_scope()