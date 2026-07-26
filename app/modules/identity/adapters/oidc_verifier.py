"""Adapter for TokenVerifier: validates JWTs against Keycloak's JWKS endpoint.

Assumes a Keycloak protocol mapper adds `care_home_id` and `role` as custom claims on
the access token -- see governance/decision-log.md. Realm export lives alongside
docker-compose.yml once Keycloak setup lands (Week 2-3 per the roadmap).
"""

import time

import httpx
from jose import jwt

from app.modules.identity.ports import TokenClaims, TokenVerifier
from app.shared.exceptions import UnauthenticatedError

_JWKS_CACHE_TTL_SECONDS = 3600


class KeycloakTokenVerifier(TokenVerifier):
    def __init__(self, issuer: str, audience: str):
        self._issuer = issuer
        self._audience = audience
        self._jwks: dict | None = None
        self._jwks_fetched_at: float = 0.0

    async def _get_jwks(self) -> dict:
        stale = time.monotonic() - self._jwks_fetched_at > _JWKS_CACHE_TTL_SECONDS
        if self._jwks is None or stale:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._issuer}/protocol/openid-connect/certs")
                response.raise_for_status()
                self._jwks = response.json()
                self._jwks_fetched_at = time.monotonic()
        return self._jwks

    async def verify(self, bearer_token: str) -> TokenClaims:
        jwks = await self._get_jwks()
        try:
            claims = jwt.decode(bearer_token, jwks, audience=self._audience, issuer=self._issuer)
        except jwt.JWTError as exc:
            raise UnauthenticatedError(f"invalid token: {exc}") from exc

        try:
            return TokenClaims(
                subject=claims["sub"],
                email=claims.get("email", ""),
                display_name=claims.get("name", claims.get("preferred_username", "")),
                care_home_id=claims["care_home_id"],
                role=claims["role"],
            )
        except KeyError as exc:
            raise UnauthenticatedError(f"token missing required claim: {exc}") from exc
