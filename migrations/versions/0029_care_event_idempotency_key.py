"""care_events.idempotency_key -- safe client-side retry of POST /care-recording/events

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-05

Mirrors observations.idempotency_key (migration 0009's Observation model) exactly:
a nullable, unique key the client generates once per care entry and resends on every
retry attempt. Postgres treats multiple NULLs as distinct under a UNIQUE constraint,
so ordinary inserts that don't supply a key are unaffected -- this only blocks a
second insert that reuses the same key, which is precisely the "did my last request
actually go through" case an offline-durable client needs answered safely.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE care_events ADD COLUMN idempotency_key VARCHAR(255) UNIQUE;")


def downgrade() -> None:
    op.execute("ALTER TABLE care_events DROP COLUMN idempotency_key;")
