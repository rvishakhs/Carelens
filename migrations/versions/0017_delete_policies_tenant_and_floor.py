"""add missing DELETE row-level-security policies (tenant- and floor-aware)

Revision ID: 0017
Revises: 0016
Create Date: manually authored -- fixes a gap reintroduced by 0013

Migration 0010's tenant_isolation loop created SELECT + INSERT + UPDATE policies for
every tenant table but never a DELETE one. An earlier local migration closed that gap
with a plain `tenant_isolation_delete` policy on all 45 tenant tables -- but 0013
(floors) rewrote SELECT/INSERT/UPDATE on every resident-scoped table to also filter by
floor_id, without touching DELETE at all. Left alone, that would have been a real
regression: a user authorised for floor A could delete a resident-scoped row that
belongs to floor B in the same care home, because DELETE would still only be checked
against the old tenant-only rule.

This migration is intentionally the last one before the permissions work: it needs to
cover every table added since, including the new care_template/care_event (0014) and
AI knowledge layer (0016) tables.

Three groups, matching how each table's other policies are already shaped:
  1. Plain tenant-only tables (never got a floor_id column) -> tenant_isolation_delete.
  2. Floor-scoped tables (residents + everything in 0013/0014/0016's floor loops) ->
     tenant_and_floor_isolation_delete.
  3. Template config tables (care_home_id nullable -- NULL means a shared global
     template) -> tenant_only_delete, deliberately NOT matching NULL rows, so a
     tenant session can never delete a global template.

care_categories, ai_prompt_versions, and care_homes are deliberately left out: the
first two are system-wide reference data with RLS disabled entirely (per 0014/0016's
own comments), and deleting a care_homes row is not a supported operation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLAIN_TENANT_TABLES = [
    "users", "user_resident_links", "care_plan_versions", "care_plan_suggestions",
    "medication_stock_events", "wound_review_notes", "activities", "audit_events",
    "floors", "user_floor_links",
]

FLOOR_SCOPED_TABLES = [
    "residents",
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
    # 0014 -- care template event engine
    "care_events", "care_event_options", "care_event_measurements", "care_event_files",
    # 0016 -- AI knowledge layer
    "ai_generation_logs", "resident_ai_summaries", "resident_ai_reports",
    "resident_ai_alerts", "resident_predictions",
]

TEMPLATE_CONFIG_TABLES = [
    "care_templates", "care_template_sections", "care_template_options",
    "care_template_measurements",
]


def upgrade() -> None:
    def _sql_array(tables: list[str]) -> str:
        return ", ".join(f"'{t}'" for t in tables)

    op.execute(f"""\
DO $$
DECLARE
    tbl TEXT;
    plain_tables TEXT[] := ARRAY[{_sql_array(PLAIN_TENANT_TABLES)}];
BEGIN
    FOREACH tbl IN ARRAY plain_tables LOOP
        EXECUTE format($f$
            CREATE POLICY tenant_isolation_delete ON %I
            FOR DELETE
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        $f$, tbl);
    END LOOP;
END $$;

DO $$
DECLARE
    tbl TEXT;
    floor_tables TEXT[] := ARRAY[{_sql_array(FLOOR_SCOPED_TABLES)}];
BEGIN
    FOREACH tbl IN ARRAY floor_tables LOOP
        EXECUTE format($f$
            CREATE POLICY tenant_and_floor_isolation_delete ON %I
            FOR DELETE
            USING (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND floor_id = ANY (
                    string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
                )
            );
        $f$, tbl);
    END LOOP;
END $$;

DO $$
DECLARE
    tbl TEXT;
    template_tables TEXT[] := ARRAY[{_sql_array(TEMPLATE_CONFIG_TABLES)}];
BEGIN
    FOREACH tbl IN ARRAY template_tables LOOP
        EXECUTE format($f$
            CREATE POLICY tenant_only_delete ON %I
            FOR DELETE
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        $f$, tbl);
    END LOOP;
END $$;
""")


def downgrade() -> None:
    for tbl in TEMPLATE_CONFIG_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_only_delete ON {tbl};")
    for tbl in reversed(FLOOR_SCOPED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_and_floor_isolation_delete ON {tbl};")
    for tbl in PLAIN_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_delete ON {tbl};")
