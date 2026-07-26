"""tenant isolation RLS policies on every tenant table

Revision ID: 0010
Revises: 0009
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 21. ROW-LEVEL SECURITY — applied generically to every tenant table
-- =====================================================================
-- Pattern: every table with a care_home_id column gets RLS enabled,
-- forced (so even the owner role is bound by it in testing), and a
-- policy that resolves to zero rows when app.care_home_id is unset.
-- Writes are additionally checked so a session can't insert/update a
-- row tagged with a different care_home_id than the one it's scoped to.

DO $$
DECLARE
    tbl TEXT;
    tenant_tables TEXT[] := ARRAY[
        'users', 'user_resident_links', 'residents', 'resident_contacts',
        'resident_consents', 'resident_life_history', 'resident_preferences',
        'resident_daily_routines', 'resident_allergies', 'resident_diagnoses',
        'advance_care_directives', 'care_plans', 'care_plan_versions',
        'care_plan_suggestions', 'food_intake_records', 'fluid_intake_records',
        'nutrition_hydration_targets', 'nutrition_risk_assessments',
        'continence_records', 'continence_care_plans', 'mobility_assessments',
        'mobility_observations', 'falls_incidents', 'communication_needs',
        'communication_logs', 'wellbeing_records', 'behaviour_records',
        'mental_health_assessments', 'sleep_records', 'skin_integrity_assessments',
        'wound_records', 'wound_review_notes', 'vital_signs_records',
        'weight_records', 'pain_assessments', 'medications', 'medication_events',
        'medication_stock_events', 'activities', 'activity_participation',
        'visits_log', 'incidents', 'safeguarding_concerns', 'ai_outputs',
        'audit_events'
    ];
BEGIN
    FOREACH tbl IN ARRAY tenant_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_isolation_select ON %I
            FOR SELECT
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        $f$, tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_isolation_write ON %I
            FOR INSERT
            WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        $f$, tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_isolation_update ON %I
            FOR UPDATE
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid)
            WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        $f$, tbl);
    END LOOP;
END $$;

-- care_homes itself: a user can only see their own care home row (matched on id, not care_home_id)
ALTER TABLE care_homes ENABLE ROW LEVEL SECURITY;
ALTER TABLE care_homes FORCE ROW LEVEL SECURITY;
CREATE POLICY self_care_home_select ON care_homes
    FOR SELECT
    USING (id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);


-- =====================================================================
""")


def downgrade() -> None:

    tenant_tables = [
        'users', 'user_resident_links', 'residents', 'resident_contacts',
        'resident_consents', 'resident_life_history', 'resident_preferences',
        'resident_daily_routines', 'resident_allergies', 'resident_diagnoses',
        'advance_care_directives', 'care_plans', 'care_plan_versions',
        'care_plan_suggestions', 'food_intake_records', 'fluid_intake_records',
        'nutrition_hydration_targets', 'nutrition_risk_assessments',
        'continence_records', 'continence_care_plans', 'mobility_assessments',
        'mobility_observations', 'falls_incidents', 'communication_needs',
        'communication_logs', 'wellbeing_records', 'behaviour_records',
        'mental_health_assessments', 'sleep_records', 'skin_integrity_assessments',
        'wound_records', 'wound_review_notes', 'vital_signs_records',
        'weight_records', 'pain_assessments', 'medications', 'medication_events',
        'medication_stock_events', 'activities', 'activity_participation',
        'visits_log', 'incidents', 'safeguarding_concerns', 'ai_outputs',
        'audit_events',
    ]
    op.execute("DROP POLICY IF EXISTS self_care_home_select ON care_homes;")
    op.execute("ALTER TABLE care_homes NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE care_homes DISABLE ROW LEVEL SECURITY;")
    for tbl in reversed(tenant_tables):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_update ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_write ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
