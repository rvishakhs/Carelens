"""users: identity-bootstrap SELECT policy (care_home_id removed from JWT)

Revision ID: 0019
Revises: 0018
Create Date: manually authored

Until now, `KeycloakTokenVerifier` read `care_home_id` straight off the JWT, so
`get_current_user` always knew which tenant to scope its very first `rls_session()`
call to. Per governance/decision-log.md's 2026-08-03 entry, `care_home_id` is no
longer a token claim -- it's resolved from the local `users` table by `oidc_subject`
instead. That creates a chicken-and-egg problem `system_session()` can't solve:
`users` is tenant-scoped RLS (migration 0010), so a session with no
`app.care_home_id` set sees zero rows there too, including the very row that would
tell it which care_home_id to use.

This migration adds one narrow extra SELECT policy to `users` (not any other table):
permissive, OR'd with the existing `tenant_isolation_select`, true only when the
session-local `app.bootstrap` flag is set. `app.shared.database.bootstrap_session()`
is the only thing that sets it, and only for the single identity-resolution query in
`identity/dependencies.py` -- everything else (writes, every other tenant table)
still goes through a normal `rls_session()` once the tenant is known. The policy
widens SELECT to every care home's users, so the query on the other end must always
filter down to one row by oidc_subject; nothing about this migration makes `users`
listable cross-tenant on its own.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
CREATE POLICY identity_bootstrap_select ON users
    FOR SELECT
    USING (current_setting('app.bootstrap', true) = 'true');
""")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS identity_bootstrap_select ON users;")
