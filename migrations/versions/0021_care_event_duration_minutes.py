"""care_events.duration_minutes -- staff time spent per recorded care event

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable at the DB level (existing rows have no value to backfill), but the
    # care_recording API's CareEventCreate schema marks it required -- mandatory is
    # enforced at the app boundary, the same split already used for e.g.
    # care_templates.requires_note. Lets staff time on each recorded task feed
    # resident-level staffing/resource-need reporting.
    op.execute("""\
ALTER TABLE care_events
    ADD COLUMN duration_minutes SMALLINT
    CHECK (duration_minutes IS NULL OR duration_minutes > 0);
""")


def downgrade() -> None:
    op.execute("ALTER TABLE care_events DROP COLUMN duration_minutes;")
