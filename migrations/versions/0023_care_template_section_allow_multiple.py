"""care_template_sections.allow_multiple -- single vs multi-select sections

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every section in the seeded library (migration 0015) is one of 9 distinct
    # names; auditing them shows only "Food" genuinely allows more than one answer
    # (a resident can eat cereal AND toast) -- Engagement/Result/Outcome/Amount/
    # Assistance Level/Amount Eaten/Severity/Bristol Stool Type are all mutually
    # exclusive scales, so they default to single-select (radio) and "Food" is the
    # one opt-in exception.
    op.execute("ALTER TABLE care_template_sections ADD COLUMN allow_multiple BOOLEAN NOT NULL DEFAULT false;")
    op.execute("UPDATE care_template_sections SET allow_multiple = true WHERE name = 'Food';")


def downgrade() -> None:
    op.execute("ALTER TABLE care_template_sections DROP COLUMN allow_multiple;")
