"""AI-generated knowledge layer, separate from clinical records

Revision ID: 0016
Revises: 0015
Create Date: auto-generated from tested m14_ai_knowledge_layer.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- =====================================================================
-- Migration 0016 — AI-Generated Knowledge Layer
-- =====================================================================
-- Implements the separation you specified: original care records (from
-- care_events and the domain-specific clinical tables) are never
-- modified by AI. AI only reads them and writes into its OWN tables,
-- fully traceable back to what it read, when, and with which model.
--
-- This supersedes the single generic `ai_outputs` table from migration
-- 0009 with the more specific set of tables you described. `ai_outputs`
-- is left in place (nothing in Phase 1 that reads it breaks), but new
-- development should write to the tables below, which distinguish
-- summaries/reports (descriptive) from alerts (actionable) and
-- predictions (forward-looking) — different consumers, different
-- lifecycles, different review workflows.
--
-- Traceability, per your requirement: every row here can answer
-- "generated from which N events, over what period, by which model,
-- when" without ambiguity — ai_prompt_versions + ai_generation_logs
-- give you the audit trail; the *_summaries/*_reports/*_alerts/*_predictions
-- tables each carry their own provenance fields directly so a single
-- row is self-describing without a join for the common case.
--
-- Versioning, per your requirement: editing a care_event never rewrites
-- an existing AI summary. A new summary is inserted with
-- superseded_by pointing forward from the old one (or, equivalently,
-- supersedes_id pointing back) — old summaries are archived, not lost.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 14.1 Prompt version registry — one row per prompt template version
--      actually used, so a report's prompt_version_id is a real FK,
--      not a loose text field that can drift out of sync with reality.
-- ---------------------------------------------------------------------

CREATE TABLE ai_prompt_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type     TEXT NOT NULL,        -- 'daily_summary' | 'nutrition_report' | 'risk_alert' | ...
    version_label   TEXT NOT NULL,        -- 'v1', 'v2', 'v2.1' — matches the file in prompts/ in your repo
    prompt_text     TEXT NOT NULL,        -- the actual template, for exact reproducibility
    model_name      TEXT NOT NULL,        -- 'claude-sonnet-4-6', etc.
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (report_type, version_label)
);

-- ---------------------------------------------------------------------
-- 14.2 Generation log — one row per AI generation RUN (whether or not
--      it produced a summary/report/alert), independent of the
--      report-specific tables below. This is the layer for "did the
--      07:00 job run for every resident last night" operational
--      monitoring, and it's the audit trail for cost/latency/failures.
-- ---------------------------------------------------------------------

CREATE TABLE ai_generation_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    floor_id            UUID REFERENCES floors(id),
    resident_id         UUID REFERENCES residents(id),
    report_type         TEXT NOT NULL,
    prompt_version_id   UUID NOT NULL REFERENCES ai_prompt_versions(id),
    input_event_ids      JSONB NOT NULL DEFAULT '[]',  -- [{"table":"care_events","id":"..."}]
    input_event_count    INTEGER NOT NULL DEFAULT 0,
    period_start         TIMESTAMPTZ,
    period_end            TIMESTAMPTZ,
    status                TEXT NOT NULL DEFAULT 'completed',  -- 'completed' | 'failed' | 'skipped_no_data'
    error_message          TEXT,
    latency_ms              INTEGER,
    started_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at              TIMESTAMPTZ,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 14.3 Summaries — daily / weekly / monthly narrative rollups
-- ---------------------------------------------------------------------

CREATE TABLE resident_ai_summaries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    floor_id            UUID REFERENCES floors(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    summary_type        TEXT NOT NULL,        -- 'daily' | 'weekly' | 'monthly' | 'shift_handover'
    period_start         TIMESTAMPTZ NOT NULL,
    period_end            TIMESTAMPTZ NOT NULL,
    generation_log_id      UUID NOT NULL REFERENCES ai_generation_logs(id),
    prompt_version_id       UUID NOT NULL REFERENCES ai_prompt_versions(id),
    input_event_count        INTEGER NOT NULL DEFAULT 0,
    summary_text               TEXT NOT NULL,
    supersedes_id                UUID REFERENCES resident_ai_summaries(id),  -- points to the version this replaces
    is_current                     BOOLEAN NOT NULL DEFAULT true,
    feedback_rating                 SMALLINT CHECK (feedback_rating IN (-1, 0, 1)),
    feedback_comment                  TEXT,
    feedback_by                         UUID REFERENCES users(id),
    feedback_at                           TIMESTAMPTZ,
    generated_at                            TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                                TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                                  TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- 14.4 Domain reports — nutrition, hydration, sleep, continence,
--      medication, activity, mobility, behaviour, clinical, etc.
--      One table, a `report_domain` column, rather than 9 near-identical
--      tables — these are structurally identical, only the domain and
--      content differ, so a single table with a checked domain value
--      is simpler to query across ("show me every nutrition report this
--      month") without a UNION.
-- ---------------------------------------------------------------------

CREATE TABLE resident_ai_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    floor_id            UUID REFERENCES floors(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    report_domain       TEXT NOT NULL,   -- 'nutrition' | 'hydration' | 'sleep' | 'continence' |
                                          -- 'medication' | 'activity' | 'mobility' | 'behaviour' | 'clinical'
    period_start         TIMESTAMPTZ NOT NULL,
    period_end             TIMESTAMPTZ NOT NULL,
    generation_log_id       UUID NOT NULL REFERENCES ai_generation_logs(id),
    prompt_version_id         UUID NOT NULL REFERENCES ai_prompt_versions(id),
    input_event_count          INTEGER NOT NULL DEFAULT 0,
    report_text                  TEXT NOT NULL,
    structured_findings            JSONB NOT NULL DEFAULT '{}',  -- e.g. {"avg_fluid_ml": 1200, "trend": "declining"}
    supersedes_id                    UUID REFERENCES resident_ai_reports(id),
    is_current                         BOOLEAN NOT NULL DEFAULT true,
    feedback_rating                      SMALLINT CHECK (feedback_rating IN (-1, 0, 1)),
    feedback_comment                       TEXT,
    feedback_by                              UUID REFERENCES users(id),
    feedback_at                                TIMESTAMPTZ,
    generated_at                                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                                       TIMESTAMPTZ,
    CHECK (report_domain IN (
        'nutrition', 'hydration', 'sleep', 'continence', 'medication',
        'activity', 'mobility', 'behaviour', 'clinical'
    ))
);

-- ---------------------------------------------------------------------
-- 14.5 Alerts — actionable, time-sensitive, need a human decision
-- ---------------------------------------------------------------------

CREATE TABLE resident_ai_alerts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    floor_id            UUID REFERENCES floors(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    alert_type          TEXT NOT NULL,        -- 'nutrition_decline' | 'fall_risk_increase' | 'mood_change' | ...
    severity             TEXT NOT NULL DEFAULT 'info',  -- 'info' | 'warning' | 'urgent'
    generation_log_id      UUID NOT NULL REFERENCES ai_generation_logs(id),
    prompt_version_id        UUID NOT NULL REFERENCES ai_prompt_versions(id),
    triggering_event_ids       JSONB NOT NULL DEFAULT '[]',
    alert_text                   TEXT NOT NULL,
    status                         TEXT NOT NULL DEFAULT 'open',  -- 'open' | 'acknowledged' | 'resolved' | 'dismissed'
    acknowledged_by                  UUID REFERENCES users(id),
    acknowledged_at                    TIMESTAMPTZ,
    resolution_note                      TEXT,
    generated_at                           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                                   TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- 14.6 Predictions — forward-looking, explicitly separated from alerts
--      because they carry a confidence/probability and a longer horizon,
--      and because MHRA-boundary wording matters most here: predictions
--      must always read as "a pattern to review", never a diagnosis.
-- ---------------------------------------------------------------------

CREATE TABLE resident_predictions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    floor_id            UUID REFERENCES floors(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    prediction_type     TEXT NOT NULL,        -- 'deterioration_risk' | 'readmission_risk' | ...
    horizon_days         INTEGER,
    confidence             NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
    generation_log_id        UUID NOT NULL REFERENCES ai_generation_logs(id),
    prompt_version_id          UUID NOT NULL REFERENCES ai_prompt_versions(id),
    input_event_ids               JSONB NOT NULL DEFAULT '[]',
    prediction_text                 TEXT NOT NULL,
    recommended_action                 TEXT,   -- always phrased as "prompts for clinical review" (MHRA boundary)
    status                               TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'expired' | 'superseded'
    generated_at                           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                               TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                                 TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- 14.7 floor_id sync triggers (same pattern as migrations 0013/0014)
-- ---------------------------------------------------------------------

DO $$
DECLARE
    tbl TEXT;
    ai_resident_tables TEXT[] := ARRAY[
        'ai_generation_logs', 'resident_ai_summaries', 'resident_ai_reports',
        'resident_ai_alerts', 'resident_predictions'
    ];
BEGIN
    FOREACH tbl IN ARRAY ai_resident_tables LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();', tbl
        );
    END LOOP;
END $$;

-- updated_at triggers where the column exists
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON resident_ai_alerts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 14.8 Row-Level Security — same tenant + floor pattern as clinical data.
--      This is deliberate: AI outputs are exactly as sensitive as the
--      records they're derived from, and get exactly the same isolation.
-- ---------------------------------------------------------------------

DO $$
DECLARE
    tbl TEXT;
    ai_tables TEXT[] := ARRAY[
        'ai_generation_logs', 'resident_ai_summaries', 'resident_ai_reports',
        'resident_ai_alerts', 'resident_predictions'
    ];
BEGIN
    FOREACH tbl IN ARRAY ai_tables LOOP
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

-- ai_prompt_versions: system-level reference data, same treatment as care_categories
-- (no care_home_id — prompt templates are shared configuration, not resident data)

-- ---------------------------------------------------------------------
-- 14.9 Indexes for the query patterns this layer is built for
-- ---------------------------------------------------------------------

CREATE INDEX idx_ai_summaries_resident_current ON resident_ai_summaries (resident_id, summary_type, is_current) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_summaries_period ON resident_ai_summaries (resident_id, period_start DESC);
CREATE INDEX idx_ai_reports_resident_domain_current ON resident_ai_reports (resident_id, report_domain, is_current) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_alerts_resident_status ON resident_ai_alerts (resident_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_alerts_floor_open ON resident_ai_alerts (floor_id, status) WHERE status = 'open';
CREATE INDEX idx_predictions_resident_active ON resident_predictions (resident_id, status) WHERE status = 'active';
CREATE INDEX idx_generation_logs_resident_time ON ai_generation_logs (resident_id, started_at DESC);
""")


def downgrade() -> None:
    for tbl in [
        "resident_predictions", "resident_ai_alerts", "resident_ai_reports",
        "resident_ai_summaries", "ai_generation_logs", "ai_prompt_versions",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")
