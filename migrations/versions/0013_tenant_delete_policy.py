"""add missing DELETE row-level-security policy on every tenant table

Revision ID: 0013
Revises: 0012
Create Date: manually authored -- fixes a gap in 0010

0010's tenant_isolation loop created SELECT + INSERT + UPDATE policies for every
tenant table but never a DELETE one. With RLS forced and no policy matching a given
command, Postgres silently filters that command to zero matching rows rather than
erroring -- so a DELETE on, say, audit_events looked like it "succeeded" (0 rows
affected) without ever reaching the row, meaning the append-only trigger
(reject_audit_tamper(), 0009) never got a chance to fire and reject it with a clear
error. The data was never at risk (nothing matched, nothing deleted), but the missing
policy meant the failure mode was a silent no-op instead of a loud, debuggable
rejection -- surfaced by tests/rbac/test_rls_isolation.py::test_audit_events_reject_delete.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_TABLES = [
    "users", "user_resident_links", "residents", "resident_contacts",
    "resident_consents", "resident_life_history", "resident_preferences",
    "resident_daily_routines", "resident_allergies", "resident_diagnoses",
    "advance_care_directives", "care_plans", "care_plan_versions",
    "care_plan_suggestions", "food_intake_records", "fluid_intake_records",
    "nutrition_hydration_targets", "nutrition_risk_assessments",
    "continence_records", "continence_care_plans", "mobility_assessments",
    "mobility_observations", "falls_incidents", "communication_needs",
    "communication_logs", "wellbeing_records", "behaviour_records",
    "mental_health_assessments", "sleep_records", "skin_integrity_assessments",
    "wound_records", "wound_review_notes", "vital_signs_records",
    "weight_records", "pain_assessments", "medications", "medication_events",
    "medication_stock_events", "activities", "activity_participation",
    "visits_log", "incidents", "safeguarding_concerns", "ai_outputs",
    "audit_events",
]


def upgrade() -> None:
    tables_literal = ", ".join(f"'{t}'" for t in _TENANT_TABLES)
    op.execute(f"""\
DO $$
DECLARE
    tbl TEXT;
    tenant_tables TEXT[] := ARRAY[{tables_literal}];
BEGIN
    FOREACH tbl IN ARRAY tenant_tables LOOP
        EXECUTE format($f$
            CREATE POLICY tenant_isolation_delete ON %I
            FOR DELETE
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        $f$, tbl);
    END LOOP;
END $$;
""")


def downgrade() -> None:
    for tbl in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_delete ON {tbl};")
