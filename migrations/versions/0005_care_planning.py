"""care plans, versions, AI suggestions

Revision ID: 0005
Revises: 0004
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 6. CARE PLANNING: PLANS, VERSIONS, AI SUGGESTIONS
-- =====================================================================

CREATE TABLE care_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    domain          care_plan_domain NOT NULL,
    goal            TEXT NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    review_due      DATE,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (resident_id, domain, current_version)
);

CREATE TABLE care_plan_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    care_plan_id    UUID NOT NULL REFERENCES care_plans(id),
    version_number  INTEGER NOT NULL,
    content         TEXT NOT NULL,          -- the full plan text at this version
    changed_by      UUID REFERENCES users(id),
    change_reason   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (care_plan_id, version_number)
);

CREATE TABLE care_plan_suggestions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    care_plan_id        UUID NOT NULL REFERENCES care_plans(id),
    proposed_change     TEXT NOT NULL,
    triggering_evidence JSONB NOT NULL DEFAULT '[]', -- array of source record IDs/types
    model_version       TEXT NOT NULL,
    status              care_plan_suggestion_status NOT NULL DEFAULT 'pending',
    reviewed_by         UUID REFERENCES users(id),
    reviewed_at         TIMESTAMPTZ,
    review_notes        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);


-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP TABLE IF EXISTS care_plan_suggestions CASCADE;")
    op.execute("DROP TABLE IF EXISTS care_plan_versions CASCADE;")
    op.execute("DROP TABLE IF EXISTS care_plans CASCADE;")
