"""Interfaces identity depends on. Auth is never hand-rolled -- this is the one seam
through which an external OIDC provider (Keycloak, Auth0, ...) is consumed."""

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenClaims:
    """Normalised claims extracted from a verified ID/access token. `care_home_id` and
    `role` are expected as custom claims (Keycloak protocol mappers) -- see
    governance/decision-log.md for why role lives in the token vs. only in our DB."""

    subject: str
    email: str
    display_name: str
    care_home_id: str
    role: str


class TokenVerifier(abc.ABC):
    """Port for verifying a bearer token against the OIDC provider. Concrete adapter:
    app/modules/identity/adapters/oidc_verifier.py."""

    @abc.abstractmethod
    async def verify(self, bearer_token: str) -> TokenClaims: ...