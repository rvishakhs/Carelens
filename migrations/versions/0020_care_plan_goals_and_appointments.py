"""structured care plan goals + appointments (GP/hospital/etc)

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE can't run in the same transaction as the rest
    # of this migration (same constraint as migration 0013's admin/headoffice
    # roles) -- isolated in its own autocommit block. 'personal' gives
    # aspiration-style goals ("see my grandchildren more", "get back to
    # gardening") a home that isn't one of the 11 clinical domains.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE care_plan_domain ADD VALUE IF NOT EXISTS 'personal';")

    op.execute("""\
-- =====================================================================
-- Migration 0020 -- Structured Care Plan Goals + Appointments
-- =====================================================================
-- care_plans.goal (migration 0005) is a single free-text field per
-- domain -- fine for "what are we doing", not enough for "what outcome
-- are we tracking and how is it trending". care_plan_goals adds a
-- goal -> baseline -> target -> status sub-entity underneath a care
-- plan, so goal drift over time (declining/improving/achieved) becomes
-- a real signal the AI layer (migration 0016) can reference as
-- structured_findings / triggering evidence, not something it has to
-- infer from free text.
--
-- appointments closes the "care journey" gap -- GP/hospital/therapy
-- visits didn't exist anywhere in the schema.
--
-- Both follow the same resident-scoped pattern as every clinical table
-- since migration 0013: care_home_id + denormalised floor_id (synced
-- from the resident via the existing sync_floor_id_from_resident()
-- trigger) + tenant-and-floor RLS.
-- =====================================================================

CREATE TYPE care_plan_goal_status AS ENUM (
    'not_started', 'in_progress', 'improving', 'maintained', 'declining',
    'achieved', 'discontinued'
);

CREATE TYPE appointment_type AS ENUM (
    'gp', 'hospital', 'physiotherapy', 'dentist', 'optician', 'chiropody',
    'mental_health', 'specialist', 'other'
);

CREATE TYPE appointment_status AS ENUM (
    'scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled'
);

-- ---------------------------------------------------------------------
-- 20.1 care_plan_goals
-- ---------------------------------------------------------------------

CREATE TABLE care_plan_goals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    floor_id        UUID REFERENCES floors(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    care_plan_id    UUID NOT NULL REFERENCES care_plans(id),
    goal_text       TEXT NOT NULL,
    baseline        TEXT,           -- "walks ~30m with frame and supervision"
    target          TEXT,           -- "walk 20m independently"
    measurement     TEXT,           -- what's tracked to judge progress
    status          care_plan_goal_status NOT NULL DEFAULT 'not_started',
    set_by          UUID REFERENCES users(id),
    set_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    review_date     DATE,
    achieved_date   DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- 20.2 appointments
-- ---------------------------------------------------------------------

CREATE TABLE appointments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    floor_id            UUID REFERENCES floors(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    appointment_type    appointment_type NOT NULL,
    scheduled_at        TIMESTAMPTZ NOT NULL,
    provider_name       TEXT,
    location            TEXT,
    reason              TEXT NOT NULL,
    status              appointment_status NOT NULL DEFAULT 'scheduled',
    outcome             TEXT,
    transport_required  BOOLEAN NOT NULL DEFAULT false,
    escort_required     BOOLEAN NOT NULL DEFAULT false,
    family_informed     BOOLEAN NOT NULL DEFAULT false,
    recorded_by         UUID REFERENCES users(id),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- 20.3 floor_id sync triggers (same pattern as migrations 0013/0016)
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON care_plan_goals
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();
CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON care_plan_goals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 20.4 Row-Level Security -- same tenant + floor pattern as every other
--      clinical table since migration 0013.
-- ---------------------------------------------------------------------

DO $$
DECLARE
    tbl TEXT;
    new_tables TEXT[] := ARRAY['care_plan_goals', 'appointments'];
BEGIN
    FOREACH tbl IN ARRAY new_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_and_floor_isolation_select ON %I
            FOR SELECT
            USING (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND (
                    floor_id IS NULL
                    OR floor_id = ANY (
                        string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
                    )
                )
            );
        $f$, tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_and_floor_isolation_write ON %I
            FOR INSERT
            WITH CHECK (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND (
                    floor_id IS NULL
                    OR floor_id = ANY (
                        string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
                    )
                )
            );
        $f$, tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_and_floor_isolation_update ON %I
            FOR UPDATE
            USING (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND (
                    floor_id IS NULL
                    OR floor_id = ANY (
                        string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
                    )
                )
            )
            WITH CHECK (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND (
                    floor_id IS NULL
                    OR floor_id = ANY (
                        string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
                    )
                )
            );
        $f$, tbl);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------
-- 20.5 Indexes
-- ---------------------------------------------------------------------

CREATE INDEX idx_care_plan_goals_plan ON care_plan_goals (care_plan_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_care_plan_goals_resident_status ON care_plan_goals (resident_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_appointments_resident_scheduled ON appointments (resident_id, scheduled_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_appointments_floor_status ON appointments (floor_id, status) WHERE deleted_at IS NULL;
""")


def downgrade() -> None:
    for tbl in ["care_plan_goals", "appointments"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_and_floor_isolation_select ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS tenant_and_floor_isolation_write ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS tenant_and_floor_isolation_update ON {tbl};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_sync_floor_id ON {tbl};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_set_updated_at ON {tbl};")
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")

    op.execute("DROP TYPE IF EXISTS appointment_status;")
    op.execute("DROP TYPE IF EXISTS appointment_type;")
    op.execute("DROP TYPE IF EXISTS care_plan_goal_status;")

    # NOTE: 'personal' cannot be cleanly removed from care_plan_domain
    # without rebuilding the type (see migration 0013's downgrade for the
    # same situation with user_role) -- left in place deliberately.
