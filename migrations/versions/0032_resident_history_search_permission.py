"""Add the resident-history search permission to the live permission registry.

Revision ID: 0032
Revises: 0031
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSION = "search_resident_history"
_ROLES = ("nurse", "manager", "admin", "headoffice", "system_admin")


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("INSERT INTO permissions (code) VALUES (:code) ON CONFLICT (code) DO NOTHING"),
        {"code": _PERMISSION},
    )
    for role in _ROLES:
        connection.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role, permission_id)
                SELECT :role, id FROM permissions WHERE code = :code
                ON CONFLICT (role, permission_id) DO NOTHING
                """
            ),
            {"role": role, "code": _PERMISSION},
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id = (SELECT id FROM permissions WHERE code = :code)
            """
        ),
        {"code": _PERMISSION},
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": _PERMISSION})
