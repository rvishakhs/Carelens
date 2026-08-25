"""Move Personal Safety & Environment to right after Personal Care

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
-- Park it out of the way first so the +1 bump below can't collide with its old
-- position (11), then bump everything currently between Personal Care (2) and
-- Activities (10) up by one, then drop it into the newly-freed slot 3.
UPDATE care_categories SET sort_order = 999 WHERE name = 'Personal Safety & Environment';
UPDATE care_categories SET sort_order = sort_order + 1 WHERE sort_order BETWEEN 3 AND 10;
UPDATE care_categories SET sort_order = 3 WHERE name = 'Personal Safety & Environment';
""")


def downgrade() -> None:
    op.execute("""
UPDATE care_categories SET sort_order = 999 WHERE name = 'Personal Safety & Environment';
UPDATE care_categories SET sort_order = sort_order - 1 WHERE sort_order BETWEEN 4 AND 11;
UPDATE care_categories SET sort_order = 11 WHERE name = 'Personal Safety & Environment';
""")
