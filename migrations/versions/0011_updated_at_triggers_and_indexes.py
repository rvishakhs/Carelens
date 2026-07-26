"""generic updated_at triggers plus the core query-path indexes

Revision ID: 0011
Revises: 0010
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 22. UPDATED-AT TRIGGERS — applied to every table that has the column
-- =====================================================================

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT table_name FROM information_schema.columns
        WHERE column_name = 'updated_at' AND table_schema = 'public'
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at();', r.table_name
        );
    END LOOP;
END $$;


-- =====================================================================
-- INDEXES — the query patterns Phase 1/2 depend on
-- =====================================================================

CREATE INDEX idx_food_intake_resident_time ON food_intake_records (resident_id, recorded_at DESC);
CREATE INDEX idx_fluid_intake_resident_time ON fluid_intake_records (resident_id, recorded_at DESC);
CREATE INDEX idx_continence_resident_time ON continence_records (resident_id, recorded_at DESC);
CREATE INDEX idx_mobility_obs_resident_time ON mobility_observations (resident_id, recorded_at DESC);
CREATE INDEX idx_wellbeing_resident_time ON wellbeing_records (resident_id, recorded_at DESC);
CREATE INDEX idx_behaviour_resident_time ON behaviour_records (resident_id, occurred_at DESC);
CREATE INDEX idx_vitals_resident_time ON vital_signs_records (resident_id, recorded_at DESC);
CREATE INDEX idx_weight_resident_time ON weight_records (resident_id, recorded_at DESC);
CREATE INDEX idx_pain_resident_time ON pain_assessments (resident_id, assessed_at DESC);
CREATE INDEX idx_medevents_resident_time ON medication_events (resident_id, administered_at DESC);
CREATE INDEX idx_falls_resident_time ON falls_incidents (resident_id, occurred_at DESC);
CREATE INDEX idx_ai_outputs_resident_time ON ai_outputs (resident_id, generated_at DESC);
CREATE INDEX idx_audit_resident_time ON audit_events (care_home_id, entity_type, occurred_at DESC);

CREATE INDEX idx_residents_care_home ON residents (care_home_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_care_plans_resident_domain ON care_plans (resident_id, domain) WHERE deleted_at IS NULL;
CREATE INDEX idx_medications_resident_active ON medications (resident_id) WHERE is_active AND deleted_at IS NULL;

-- =====================================================================
-- End of schema
-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP INDEX IF EXISTS idx_medications_resident_active;")
    op.execute("DROP INDEX IF EXISTS idx_care_plans_resident_domain;")
    op.execute("DROP INDEX IF EXISTS idx_residents_care_home;")
    op.execute("DROP INDEX IF EXISTS idx_audit_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_ai_outputs_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_falls_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_medevents_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_pain_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_weight_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_vitals_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_behaviour_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_wellbeing_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_mobility_obs_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_continence_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_fluid_intake_resident_time;")
    op.execute("DROP INDEX IF EXISTS idx_food_intake_resident_time;")
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN
                SELECT table_name FROM information_schema.columns
                WHERE column_name = 'updated_at' AND table_schema = 'public'
            LOOP
                EXECUTE format('DROP TRIGGER IF EXISTS trg_set_updated_at ON %I;', r.table_name);
            END LOOP;
        END $$;
    """)
