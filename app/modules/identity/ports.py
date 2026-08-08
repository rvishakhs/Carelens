"""Interfaces identity depends on. Auth is never hand-rolled -- this is the one seam
through which an external OIDC provider (Keycloak, Auth0, ...) is consumed."""

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenClaims:
    """Normalised claims extracted from a verified ID/access token. Deliberately
    identity-only -- `sub`/email/display-name/`role` are things Keycloak is
    authoritative for. `care_home_id` is NOT here: it's CareLens's own tenant/app
    data, resolved from the local `users` table by `subject` once the token is
    verified (see identity/dependencies.py and governance/decision-log.md's
    2026-08-03 entry) -- Keycloak has no concept of "which care home", and putting it
    in a token would mean a manager moving someone between homes doesn't take effect
    until the token expires."""

    subject: str
    email: str
    display_name: str
    role: str


class TokenVerifier(abc.ABC):
    """Port for verifying a bearer token against the OIDC provider. Concrete adapter:
    app/modules/identity/adapters/oidc_verifier.py."""

    @abc.abstractmethod
    async def verify(self, bearer_token: str) -> TokenClaims: ...


class IdentityProviderAdmin(abc.ABC):
    """Port for provisioning accounts in the OIDC provider -- the write-side
    counterpart to TokenVerifier. Used by a manager's "add staff" flow
    (identity/service.py's create_staff_member); never by the request-authentication
    path. Concrete adapter: app/modules/identity/adapters/keycloak_admin.py."""

    @abc.abstractmethod
    async def create_user(self, *, email: str, display_name: str, role: str, temporary_password: str) -> str:
        """Creates the account (disabled MFA/email-verification flow is Keycloak's own
        concern) and assigns `role` as a realm role -- matching the fallback
        role-extraction path in KeycloakTokenVerifier._extract_role, so a freshly
        provisioned user authenticates with a usable role claim on their very first
        login with no extra protocol-mapper setup. Returns the provider's subject
        (`sub`) id, which becomes the new local user row's oidc_subject."""
        ...

    @abc.abstractmethod
    async def set_temporary_password(self, oidc_subject: str, temporary_password: str) -> None:
        """A manager's "reset password" action -- forces a reset on next login, same as
        create_user's initial password. Never called from the login path."""
        ...

    @abc.abstractmethod
    async def set_enabled(self, oidc_subject: str, enabled: bool) -> None:
        """The deactivate/reactivate counterpart to the local `users.is_active` flag --
        disabling here means the account can't obtain a new token at all, not just fail
        CareLens's own is_active check (identity/repository.py's sync_from_claims)."""
        ...