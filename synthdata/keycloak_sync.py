"""Provisions the synthetic care home's admin account in Keycloak.

identity/adapters/keycloak_admin.py's KeycloakAdminClient is async-only (it's built
for FastAPI request handlers); synthdata is deliberately synchronous (see db.py's
docstring), so this talks to the same Admin REST API through python-keycloak's sync
client instead of wrapping the async one in asyncio.run(). Logic mirrors
KeycloakAdminClient.create_user, plus a lookup-by-username so re-running the generator
against a Keycloak that already has the account (e.g. the Postgres data was dropped
and recreated but Keycloak's dev store wasn't) resets its password instead of failing
on a duplicate-user conflict.
"""

from keycloak import KeycloakAdmin, KeycloakOpenIDConnection


def create_admin_account(
    *,
    server_url: str,
    realm_name: str,
    client_id: str,
    client_secret: str,
    email: str,
    display_name: str,
    role: str,
    temporary_password: str,
) -> str:
    """Creates (or reuses) the Keycloak account for the synthetic admin user and
    returns its oidc_subject, for the generator to store as the local users row's
    oidc_subject."""
    connection = KeycloakOpenIDConnection(
        server_url=server_url,
        realm_name=realm_name,
        client_id=client_id,
        client_secret_key=client_secret,
        grant_type="client_credentials",
    )
    admin = KeycloakAdmin(connection=connection)

    existing = admin.get_users({"username": email, "exact": True})
    if existing:
        user_id = existing[0]["id"]
        admin.set_user_password(user_id, temporary_password, temporary=True)
    else:
        first_name, _, last_name = display_name.partition(" ")
        user_id = admin.create_user(
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

    # Realm-role assignment, not a custom protocol mapper -- matches the fallback path
    # in KeycloakTokenVerifier._extract_role(), so this user has a usable role claim on
    # first login with zero extra realm config.
    realm_role = admin.get_realm_role(role)
    admin.assign_realm_roles(user_id, [realm_role])
    return user_id