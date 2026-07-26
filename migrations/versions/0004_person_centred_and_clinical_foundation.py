"""life history, preferences, routines, allergies, diagnoses, advance care directives

Revision ID: 0004
Revises: 0003
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 4. PERSON-CENTRED FOUNDATIONS: LIFE HISTORY, PREFERENCES, ROUTINES
-- =====================================================================
-- This is the "This Is Me" data — the single biggest differentiator
-- between a generic records system and genuinely person-centred care.

CREATE TABLE resident_life_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    occupation      TEXT,
    family_background TEXT,
    significant_events TEXT,       -- widowhood, war service, migration, etc.
    hobbies_interests  TEXT,
    important_relationships TEXT,
    faith_religion     TEXT,
    cultural_background TEXT,
    language_preferred  TEXT,
    military_veteran    BOOLEAN NOT NULL DEFAULT false,
    free_text_narrative TEXT,      -- the open "tell us about yourself" narrative
    created_by          UUID REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at           TIMESTAMPTZ
);

CREATE TABLE resident_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    category            TEXT NOT NULL,   -- 'food', 'drink', 'routine', 'personal_care', 'social', 'environment'
    preference          TEXT NOT NULL,   -- e.g. "prefers tea over coffee", "likes curtains open at night"
    is_like              BOOLEAN NOT NULL DEFAULT true, -- false = dislike / must-avoid
    priority             SMALLINT NOT NULL DEFAULT 3,   -- 1 = critical (e.g. allergy-adjacent dislike), 5 = minor
    recorded_by          UUID REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at           TIMESTAMPTZ
);

CREATE TABLE resident_daily_routines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    routine_type    TEXT NOT NULL,   -- 'wake_time', 'bed_time', 'meal_pref_time', 'bathing_day', 'nap'
    preferred_time  TIME,
    day_of_week     SMALLINT,        -- 0=Sunday .. 6=Saturday, null = every day
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
-- 5. CLINICAL FOUNDATION: ALLERGIES, DIAGNOSES, ADVANCE CARE PLANNING
-- =====================================================================

CREATE TABLE resident_allergies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    allergen        TEXT NOT NULL,
    reaction        TEXT,
    severity        TEXT,           -- 'mild', 'moderate', 'severe', 'anaphylaxis'
    verified_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE resident_diagnoses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    condition_name  TEXT NOT NULL,
    icd10_code      TEXT,
    diagnosed_date  DATE,
    is_primary      BOOLEAN NOT NULL DEFAULT false,
    status          TEXT NOT NULL DEFAULT 'active', -- active | resolved | monitoring
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- DNACPR, ReSPECT forms, ceiling of care, preferred place of death, etc.
CREATE TABLE advance_care_directives (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id            UUID NOT NULL REFERENCES care_homes(id),
    resident_id             UUID NOT NULL REFERENCES residents(id),
    directive_type          TEXT NOT NULL,  -- 'DNACPR', 'ReSPECT', 'advance_decision', 'ceiling_of_care'
    summary                 TEXT NOT NULL,
    document_reference      TEXT,           -- link/id to scanned form in document store
    signed_by_clinician     TEXT,
    review_due              DATE,
    is_current               BOOLEAN NOT NULL DEFAULT true,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at               TIMESTAMPTZ
);


-- =====================================================================
""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS advance_care_directives CASCADE;")
    op.execute("DROP TABLE IF EXISTS resident_diagnoses CASCADE;")
    op.execute("DROP TABLE IF EXISTS resident_allergies CASCADE;")
    op.execute("DROP TABLE IF EXISTS resident_daily_routines CASCADE;")
    op.execute("DROP TABLE IF EXISTS resident_preferences CASCADE;")
    op.execute("DROP TABLE IF EXISTS resident_life_history CASCADE;")
