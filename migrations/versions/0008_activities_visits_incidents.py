"""activities, participation, visits, incidents, safeguarding

Revision ID: 0008
Revises: 0007
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 17. ACTIVITIES, SOCIAL ENGAGEMENT & VISITS
-- =====================================================================

CREATE TABLE activities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    name            TEXT NOT NULL,
    category        TEXT,                 -- 'physical', 'cognitive', 'social', 'spiritual', 'creative'
    scheduled_at    TIMESTAMPTZ,
    location        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE activity_participation (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    activity_id     UUID NOT NULL REFERENCES activities(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    attended        BOOLEAN NOT NULL DEFAULT true,
    engagement_level SMALLINT CHECK (engagement_level BETWEEN 1 AND 5),
    enjoyment_noted TEXT,
    recorded_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE visits_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    visitor_name    TEXT NOT NULL,
    relationship    TEXT,
    visited_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_minutes INTEGER,
    resident_mood_during_visit mood_state,
    notes           TEXT,
    recorded_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
-- 18. INCIDENTS & SAFEGUARDING
-- =====================================================================

CREATE TABLE incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID REFERENCES residents(id),  -- nullable: some incidents aren't resident-specific
    incident_type   incident_type NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL,
    location        TEXT,
    description     TEXT NOT NULL,
    immediate_action TEXT,
    reported_by     UUID REFERENCES users(id),
    riddor_reportable BOOLEAN NOT NULL DEFAULT false,
    cqc_notifiable  BOOLEAN NOT NULL DEFAULT false,
    family_informed BOOLEAN NOT NULL DEFAULT false,
    investigation_status TEXT NOT NULL DEFAULT 'open', -- open | in_review | closed
    investigation_outcome TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE safeguarding_concerns (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    incident_id         UUID REFERENCES incidents(id),
    category            safeguarding_category NOT NULL,
    description          TEXT NOT NULL,
    raised_by            UUID REFERENCES users(id),
    local_authority_notified BOOLEAN NOT NULL DEFAULT false,
    notified_at          TIMESTAMPTZ,
    status               TEXT NOT NULL DEFAULT 'open', -- open | investigating | closed
    outcome              TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at            TIMESTAMPTZ
);


-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP TABLE IF EXISTS safeguarding_concerns CASCADE;")
    op.execute("DROP TABLE IF EXISTS incidents CASCADE;")
    op.execute("DROP TABLE IF EXISTS visits_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS activity_participation CASCADE;")
    op.execute("DROP TABLE IF EXISTS activities CASCADE;")
