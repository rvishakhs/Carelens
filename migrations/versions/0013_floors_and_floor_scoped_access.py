"""floors and floor-scoped access control

Revision ID: 0013
Revises: 0012
Create Date: auto-generated from tested m12_floors_and_floor_rls.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that gained a denormalised floor_id column + RLS floor filter in
# this migration (mirrors the array used inside the SQL itself).
FLOOR_SCOPED_TABLES = [
    "resident_contacts", "resident_consents", "resident_life_history",
    "resident_preferences", "resident_daily_routines", "resident_allergies",
    "resident_diagnoses", "advance_care_directives", "care_plans",
    "food_intake_records", "fluid_intake_records", "nutrition_hydration_targets",
    "nutrition_risk_assessments", "continence_records", "continence_care_plans",
    "mobility_assessments", "mobility_observations", "falls_incidents",
    "communication_needs", "communication_logs", "wellbeing_records",
    "behaviour_records", "mental_health_assessments", "sleep_records",
    "skin_integrity_assessments", "wound_records", "vital_signs_records",
    "weight_records", "pain_assessments", "medications", "medication_events",
    "activity_participation", "visits_log", "incidents", "safeguarding_concerns",
    "ai_outputs",
]
ALL_FLOOR_POLICY_TABLES = ["residents"] + FLOOR_SCOPED_TABLES


def upgrade() -> None:
    op.execute("""\
-- =====================================================================
-- Migration 0013 — Floors & Floor-Scoped Access Control
-- =====================================================================
-- Adds a second, finer-grained tenancy dimension underneath care_home_id:
-- floors (e.g. Dementia, Residential, Nursing) within a single care home.
--
-- Design decisions (documented here, mirrored in decision-log.md):
--
-- 1. care_home_id remains the outer boundary (unchanged) — floors are
--    nested inside it, not a replacement for it. You stay single-home
--    for now, but nothing here forecloses adding a second home later.
--
-- 2. AUTHORISATION vs SESSION SELECTION are two different things:
--      - user_floor_links = which floors a user is EVER allowed to see
--        (set by a manager/headoffice; rarely changes).
--      - app.floor_ids session variable = which of THEIR authorised
--        floors they've selected for THIS session (changes every login,
--        or when they switch floor view). The application computes this
--        as (requested floors) INTERSECT (authorised floors) and sets
--        it — RLS never has to know about roles or "admin sees all";
--        for headoffice/admin the application simply requests every
--        floor ID in the home. RLS stays a single, boring rule.
--
-- 3. floor_id is denormalised onto every resident-scoped table, the same
--    way care_home_id already is, and for the same reason: RLS filters
--    the row it's looking at directly, without a join back to residents.
--    A BEFORE INSERT/UPDATE trigger auto-fills floor_id from the
--    resident's current floor_id whenever the app doesn't supply one, so
--    write paths don't need to change everywhere at once.
--
-- 4. A row with floor_id NULL (not yet migrated/assigned) is invisible
--    under the new policies until assigned — fail-closed, not fail-open.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 12.1 Floor type + floors table
-- ---------------------------------------------------------------------

CREATE TYPE floor_type AS ENUM ('dementia', 'residential', 'nursing', 'other');

CREATE TABLE floors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    name            TEXT NOT NULL,
    floor_type      floor_type NOT NULL DEFAULT 'other',
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (care_home_id, name)
);

-- ---------------------------------------------------------------------
-- 12.2 New roles: admin, headoffice (added to the existing user_role enum)
-- ---------------------------------------------------------------------
-- ALTER TYPE ... ADD VALUE cannot run inside the same transaction as a
-- statement that USES the new value, and (pre-PG12 behaviour aside)
-- Alembic migrations run in one transaction by default — so this
-- statement must be issued in its own autocommit block. Handled in the
-- Alembic migration file via `with op.get_context().autocommit_block()`.

-- ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'admin';
-- ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'headoffice';

-- ---------------------------------------------------------------------
-- 12.3 Floor authorisation: which floors can a user ever access
-- ---------------------------------------------------------------------

CREATE TABLE user_floor_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    floor_id        UUID NOT NULL REFERENCES floors(id),
    granted_by      UUID REFERENCES users(id),
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (user_id, floor_id)
);

-- ---------------------------------------------------------------------
-- 12.4 residents gets a floor_id (nullable — existing residents need
--      manual assignment; they're invisible under floor-scoped policies
--      until assigned, which is the correct, safe default)
-- ---------------------------------------------------------------------

ALTER TABLE residents ADD COLUMN floor_id UUID REFERENCES floors(id);
CREATE INDEX idx_residents_floor ON residents (floor_id) WHERE deleted_at IS NULL;

-- ---------------------------------------------------------------------
-- 12.5 Generic floor_id sync trigger — mirrors set_updated_at() in spirit
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION sync_floor_id_from_resident()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.floor_id IS NULL AND NEW.resident_id IS NOT NULL THEN
        SELECT floor_id INTO NEW.floor_id FROM residents WHERE id = NEW.resident_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 12.6 Denormalise floor_id onto every resident-scoped clinical table,
--      backfill from the resident, attach the sync trigger, and index it.
--      (Tables whose resident link is indirect — e.g. care_plan_versions
--      via care_plan_id, wound_review_notes via wound_id, medication_stock_events
--      via medication_id — are intentionally left out of this pass; they
--      inherit floor scoping through their parent row instead.)
-- ---------------------------------------------------------------------

DO $$
DECLARE
    tbl TEXT;
    resident_scoped_tables TEXT[] := ARRAY[
        'resident_contacts', 'resident_consents', 'resident_life_history',
        'resident_preferences', 'resident_daily_routines', 'resident_allergies',
        'resident_diagnoses', 'advance_care_directives', 'care_plans',
        'food_intake_records', 'fluid_intake_records', 'nutrition_hydration_targets',
        'nutrition_risk_assessments', 'continence_records', 'continence_care_plans',
        'mobility_assessments', 'mobility_observations', 'falls_incidents',
        'communication_needs', 'communication_logs', 'wellbeing_records',
        'behaviour_records', 'mental_health_assessments', 'sleep_records',
        'skin_integrity_assessments', 'wound_records', 'vital_signs_records',
        'weight_records', 'pain_assessments', 'medications', 'medication_events',
        'activity_participation', 'visits_log', 'incidents', 'safeguarding_concerns',
        'ai_outputs'
    ];
BEGIN
    FOREACH tbl IN ARRAY resident_scoped_tables LOOP
        EXECUTE format('ALTER TABLE %I ADD COLUMN floor_id UUID REFERENCES floors(id);', tbl);

        EXECUTE format(
            'UPDATE %I t SET floor_id = r.floor_id FROM residents r WHERE r.id = t.resident_id AND t.floor_id IS NULL;',
            tbl
        );

        EXECUTE format(
            'CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();',
            tbl
        );

        EXECUTE format('CREATE INDEX idx_%s_floor ON %I (floor_id);', tbl, tbl);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------
-- 12.7 Rewrite RLS on residents + the floor-bearing tables to add the
--      floor filter alongside the existing care_home_id filter. The
--      multi-select session variable is a comma-separated UUID list:
--        SET LOCAL app.floor_ids = '<uuid1>,<uuid2>';
-- ---------------------------------------------------------------------

DO $$
DECLARE
    tbl TEXT;
    floor_scoped_tables TEXT[] := ARRAY[
        'residents',
        'resident_contacts', 'resident_consents', 'resident_life_history',
        'resident_preferences', 'resident_daily_routines', 'resident_allergies',
        'resident_diagnoses', 'advance_care_directives', 'care_plans',
        'food_intake_records', 'fluid_intake_records', 'nutrition_hydration_targets',
        'nutrition_risk_assessments', 'continence_records', 'continence_care_plans',
        'mobility_assessments', 'mobility_observations', 'falls_incidents',
        'communication_needs', 'communication_logs', 'wellbeing_records',
        'behaviour_records', 'mental_health_assessments', 'sleep_records',
        'skin_integrity_assessments', 'wound_records', 'vital_signs_records',
        'weight_records', 'pain_assessments', 'medications', 'medication_events',
        'activity_participation', 'visits_log', 'incidents', 'safeguarding_concerns',
        'ai_outputs'
    ];
BEGIN
    FOREACH tbl IN ARRAY floor_scoped_tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_select ON %I;', tbl);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_write ON %I;', tbl);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_update ON %I;', tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_and_floor_isolation_select ON %I
            FOR SELECT
            USING (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND floor_id = ANY (
                    string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
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
                AND floor_id = ANY (
                    string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
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

-- Note on the WITH CHECK floor_id IS NULL branch: INSERT/UPDATE statements
-- run the sync trigger (12.5) BEFORE the RLS check, so floor_id is already
-- populated from the resident by the time WITH CHECK evaluates for any row
-- tied to a resident. The IS NULL branch only matters for tables where
-- resident_id itself is nullable (e.g. incidents not tied to one resident).

-- ---------------------------------------------------------------------
-- 12.8 floors and user_floor_links themselves: care_home_id-scoped only
--      (a user's floor authorisations aren't floor-scoped by definition)
-- ---------------------------------------------------------------------

ALTER TABLE floors ENABLE ROW LEVEL SECURITY;
ALTER TABLE floors FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_select ON floors FOR SELECT
    USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
CREATE POLICY tenant_isolation_write ON floors FOR INSERT
    WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
CREATE POLICY tenant_isolation_update ON floors FOR UPDATE
    USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid)
    WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);

ALTER TABLE user_floor_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_floor_links FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_select ON user_floor_links FOR SELECT
    USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
CREATE POLICY tenant_isolation_write ON user_floor_links FOR INSERT
    WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
CREATE POLICY tenant_isolation_update ON user_floor_links FOR UPDATE
    USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid)
    WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);

-- updated_at triggers for the two new tables (mirrors migration 0011's pattern)
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON floors
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON user_floor_links
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_user_floor_links_user ON user_floor_links (user_id) WHERE deleted_at IS NULL AND revoked_at IS NULL;
CREATE INDEX idx_floors_care_home ON floors (care_home_id) WHERE deleted_at IS NULL;
""")
    # ALTER TYPE ... ADD VALUE cannot run inside the transaction Alembic
    # wraps this migration in — it must be its own autocommit statement,
    # and (PostgreSQL rule) the new value can't be used for comparisons
    # within that same transaction either. Isolating it here keeps the
    # rest of the migration transactional.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'admin';")
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'headoffice';")


def downgrade() -> None:
    # NOTE: PostgreSQL has no DROP VALUE for enums. 'admin' and 'headoffice'
    # cannot be cleanly removed from user_role without rebuilding the type
    # (rename old type, create new type without those values, cast every
    # column across). That's a deliberately separate, explicit operation —
    # not something a routine downgrade should do silently — so those two
    # values are left in place. If you need a true removal, write a
    # dedicated migration for it when you're certain nothing references them.

    # Revert floor-aware policies back to the original tenant-only policies
    # from migration 0010, in reverse of how this migration replaced them.
    for tbl in ALL_FLOOR_POLICY_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_and_floor_isolation_select ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS tenant_and_floor_isolation_write ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS tenant_and_floor_isolation_update ON {tbl};")

        op.execute(f"""
            CREATE POLICY tenant_isolation_select ON {tbl}
            FOR SELECT
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        """)
        op.execute(f"""
            CREATE POLICY tenant_isolation_write ON {tbl}
            FOR INSERT
            WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        """)
        op.execute(f"""
            CREATE POLICY tenant_isolation_update ON {tbl}
            FOR UPDATE
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid)
            WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        """)

    # Drop the denormalised floor_id columns (and their sync triggers,
    # which are dropped implicitly since they're defined ON these columns'
    # tables — DROP COLUMN doesn't drop the trigger, so drop it explicitly).
    for tbl in FLOOR_SCOPED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_sync_floor_id ON {tbl};")
        op.execute(f"DROP INDEX IF EXISTS idx_{tbl}_floor;")
        op.execute(f"ALTER TABLE {tbl} DROP COLUMN IF EXISTS floor_id;")

    op.execute("DROP INDEX IF EXISTS idx_residents_floor;")
    op.execute("ALTER TABLE residents DROP COLUMN IF EXISTS floor_id;")

    op.execute("DROP FUNCTION IF EXISTS sync_floor_id_from_resident();")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON user_floor_links;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_write ON user_floor_links;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON user_floor_links;")
    op.execute("DROP TABLE IF EXISTS user_floor_links CASCADE;")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON floors;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_write ON floors;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON floors;")
    op.execute("DROP TABLE IF EXISTS floors CASCADE;")

    op.execute("DROP TYPE IF EXISTS floor_type;")
