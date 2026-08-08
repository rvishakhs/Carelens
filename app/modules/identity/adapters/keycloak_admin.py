"""Adapter for IdentityProviderAdmin: provisions accounts via Keycloak's Admin REST
API (through python-keycloak's async client, authenticating as a confidential
service-account client -- see config.py's KEYCLOAK_* settings docstring).

The write-side counterpart to oidc_verifier.py's KeycloakTokenVerifier; together
they're the only places this app talks to Keycloak directly.
"""

from keycloak import KeycloakAdmin, KeycloakOpenIDConnection

from app.modules.identity.ports import IdentityProviderAdmin


class KeycloakAdminClient(IdentityProviderAdmin):
    def __init__(self, server_url: str, realm_name: str, client_id: str, client_secret: str):
        connection = KeycloakOpenIDConnection(
            server_url=server_url,
            realm_name=realm_name,
            client_id=client_id,
            client_secret_key=client_secret,
            grant_type="client_credentials",
        )
        self._admin = KeycloakAdmin(connection=connection)

    async def create_user(self, *, email: str, display_name: str, role: str, temporary_password: str) -> str:
        first_name, _, last_name = display_name.partition(" ")
        user_id = await self._admin.a_create_user(
            {
                "username": email,
                "email": email,
                "firstName": first_name,
                "lastName": last_name or first_name,
                "enabled": True,
                "emailVerified": False,
                "credentials": [{"type": "password", "value": temporary_password, "temporary": True}],
            }
        )
        # Realm-role assignment, not a custom protocol mapper -- matches the fallback
        # path in KeycloakTokenVerifier._extract_role(), so this user has a usable
        # role claim on first login with zero extra realm config.
        realm_role = await self._admin.a_get_realm_role(role)
        await self._admin.a_assign_realm_roles(user_id, [realm_role])
        return user_id

    async def set_temporary_password(self, oidc_subject: str, temporary_password: str) -> None:
        await self._admin.a_set_user_password(oidc_subject, temporary_password, temporary=True)

    async def set_enabled(self, oidc_subject: str, enabled: bool) -> None:
        await self._admin.a_update_user(oidc_subject, {"enabled": enabled})
