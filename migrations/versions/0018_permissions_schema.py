"""DB-backed permissions: permissions + role_permissions tables

Revision ID: 0018
Revises: 0017
Create Date: manually authored

Moves role->permission mappings out of a hardcoded Python dict and into the database,
so a manager can eventually grant/revoke permissions per role without a deploy (the
schema this is building toward -- app/modules/identity/permission_registry.py is the
cached, DB-backed reader `require()` actually calls at request time).

Seed data is generated FROM app/modules/identity/permissions.py's ROLE_PERMISSIONS
dict at migration-write time, not duplicated by hand -- that dict is the annotated,
human-readable source; this migration is its one-time snapshot into rows. Editing
permissions after this point happens via the permissions/role_permissions tables
directly (or a future admin UI), not by re-running this migration.

System-wide reference data, like care_categories/ai_prompt_versions -- no
care_home_id, no RLS. A permission is a permission everywhere.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,
    category    TEXT,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE role_permissions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role          user_role NOT NULL,
    permission_id UUID NOT NULL REFERENCES permissions(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (role, permission_id)
);

CREATE INDEX idx_role_permissions_role ON role_permissions (role);
""")

    # Seed from the same source of truth the app already uses -- see this file's
    # docstring for why importing application code from a migration is deliberate
    # here, not an oversight.
    from app.modules.identity.permissions import ROLE_PERMISSIONS, Permission

    connection = op.get_bind()

    permission_ids: dict[str, str] = {}
    for permission in Permission:
        result = connection.execute(
            sa.text("INSERT INTO permissions (code) VALUES (:code) RETURNING id"), {"code": permission.value}
        )
        permission_ids[permission.value] = result.scalar_one()

    for role, permission_set in ROLE_PERMISSIONS.items():
        for permission in permission_set:
            # Postgres casts the text parameter to `user_role` implicitly here since
            # there's no explicit ::type annotation forcing a mismatched cast (unlike
            # going through a typed sa.table() insert, which triggered exactly that).
            connection.execute(
                sa.text("INSERT INTO role_permissions (role, permission_id) VALUES (:role, :permission_id)"),
                {"role": role.value, "permission_id": permission_ids[permission.value]},
            )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS role_permissions CASCADE;")
    op.execute("DROP TABLE IF EXISTS permissions CASCADE;")
