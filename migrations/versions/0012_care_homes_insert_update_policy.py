
"""care_homes: add missing INSERT/UPDATE row-level-security policies

Revision ID: 0012
Revises: 0011
Create Date: manually authored -- fixes a gap in 0010

care_homes got RLS ENABLE + FORCE plus a SELECT-only policy in 0010, unlike every
other tenant table (which gets SELECT + INSERT + UPDATE). With RLS forced and no
INSERT/UPDATE policy defined, Postgres denies those commands outright for any role
without BYPASSRLS -- invisible during dev because the bootstrap Postgres role has
BYPASSRLS, but breaks the moment a properly locked-down app role tries to create a
care home (surfaced by tests/rbac/test_rls_isolation.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
CREATE POLICY self_care_home_insert ON care_homes
    FOR INSERT
    WITH CHECK (id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);

CREATE POLICY self_care_home_update ON care_homes
    FOR UPDATE
    USING (id = NULLIF(current_setting('app.care_home_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
""")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS self_care_home_update ON care_homes;")
    op.execute("DROP POLICY IF EXISTS self_care_home_insert ON care_homes;")
