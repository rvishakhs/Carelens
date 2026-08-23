"""care_events.summary -- auto-generated narrative text per recorded event

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composed server-side at record time from the template name + the selected
    # option labels + measurement values (service.py's _build_summary) -- every event
    # gets one regardless of whether staff typed a free-text note, so there's always a
    # human-readable sentence to embed later (the note column stays pure staff text).
    op.execute("ALTER TABLE care_events ADD COLUMN summary TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE care_events DROP COLUMN summary;")
