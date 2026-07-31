"""Adapter for TokenVerifier: validates JWTs against Keycloak's JWKS endpoint.

Assumes a Keycloak protocol mapper adds `care_home_id` as a custom claim on the access
token -- there's no generic Keycloak concept for "which tenant", so this one has to be
custom (see governance/decision-log.md for the realm setup this expects).

`role` is read two ways, in order: a custom `role` claim if present (lets you assign
exactly one of this app's Role values without relying on Keycloak's realm-role model),
falling back to Keycloak's default `realm_access.roles` array intersected against the
app's known Role values (so a vanilla realm-roles setup works without a bespoke
protocol mapper too). Floor authorisation is deliberately NOT read from the token --
it comes from the user_floor_links table (migrations/versions/0013), resolved fresh on
every login, so revoking a floor takes effect immediately rather than waiting for a
token to expire.
"""

import time

import httpx
from jose import jwt

from app.modules.identity.models import Role
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
            role = self._extract_role(claims)
            return TokenClaims(
                subject=claims["sub"],
                email=claims.get("email", ""),
                display_name=claims.get("name", claims.get("preferred_username", "")),
                care_home_id=claims["care_home_id"],
                role=role,
            )
        except KeyError as exc:
            raise UnauthenticatedError(f"token missing required claim: {exc}") from exc

    def _extract_role(self, claims: dict) -> str:
        if "role" in claims:
            return str(claims["role"])

        realm_roles = set(claims.get("realm_access", {}).get("roles", []))
        known_roles = {r.value for r in Role}
        matched = known_roles & realm_roles
        if not matched:
            raise UnauthenticatedError(
                "token has no usable role: expected a custom 'role' claim or a realm "
                f"role matching one of {sorted(known_roles)}"
            )
        if len(matched) > 1:
            raise UnauthenticatedError(f"token has multiple app roles, expected exactly one: {sorted(matched)}")
        return matched.pop()
