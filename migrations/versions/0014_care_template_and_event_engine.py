"""metadata-driven care template and event engine

Revision ID: 0014
Revises: 0013
Create Date: auto-generated from tested m13_care_templates_and_events.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- =====================================================================
-- Migration 0014 — Metadata-Driven Care Template & Event Engine
-- =====================================================================
-- This does NOT replace the domain-specific tables from migrations
-- 0006/0007 (food_intake_records, continence_records, etc.) — those
-- stay as your structured, strongly-typed clinical tables and are still
-- the right home for anything with well-defined fields (a BP reading, a
-- Waterlow score). This engine is for the tap-driven, configurable
-- "tile" recording UI described in your notes: carers tap options on a
-- template (Breakfast -> Cooked Breakfast / Tea / Ate Everything) rather
-- than typing, and the shape of each template is data, not code, so a
-- manager can add a new option without a deployment.
--
-- Layering (per your "AI never owns clinical data" principle):
--   care_categories        -- top-level grouping (Nutrition, Mobility, ...)
--     care_templates        -- a recordable "thing" (Breakfast, Bingo, Morning Meds)
--       care_template_sections     -- optional grouping within a template
--         care_template_options    -- tappable choices within a section
--       care_template_measurements -- optional numeric/text/bool fields
--
--   care_events             -- one carer's tap-through of a template, for one resident
--     care_event_options     -- which options they selected
--     care_event_measurements-- any measurement values they entered
--     care_event_files       -- any photo/attachment on the event
--
-- Templates are reference/configuration data, not resident data:
-- care_home_id is NULLABLE on care_templates — NULL means a global
-- template available to every home; a non-null value means a
-- home-specific customisation. This lets you ship a sensible default
-- template library without hardcoding it as application code, and lets
-- a home add its own templates later without touching global ones.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 13.1 Template metadata (configuration, not resident data)
-- ---------------------------------------------------------------------

CREATE TABLE care_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,      -- 'Nutrition', 'Mobility', 'Continence', ...
    icon            TEXT,
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE care_templates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID REFERENCES care_homes(id),  -- NULL = global template
    category_id         UUID NOT NULL REFERENCES care_categories(id),
    name                TEXT NOT NULL,             -- 'Breakfast', 'Morning Medication Round', 'Bingo'
    description         TEXT,
    requires_note       BOOLEAN NOT NULL DEFAULT false,
    sort_order          SMALLINT NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

CREATE TABLE care_template_sections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID REFERENCES care_homes(id),   -- copied from parent template for RLS
    template_id     UUID NOT NULL REFERENCES care_templates(id),
    name            TEXT NOT NULL,             -- 'Food', 'Drink', 'Amount Eaten'
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE care_template_options (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID REFERENCES care_homes(id),   -- copied from parent template for RLS
    section_id      UUID NOT NULL REFERENCES care_template_sections(id),
    label           TEXT NOT NULL,             -- 'Cooked Breakfast', 'Tea', 'Ate Everything', 'Refused'
    value_code      TEXT,                      -- stable machine code, independent of label wording
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    requires_note   BOOLEAN NOT NULL DEFAULT false,  -- e.g. force a note when 'Refused' is picked
    triggers_alert  BOOLEAN NOT NULL DEFAULT false,  -- e.g. 'Refused' feeds change-detection later
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE care_template_measurements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID REFERENCES care_homes(id),   -- copied from parent template for RLS
    template_id     UUID NOT NULL REFERENCES care_templates(id),
    name            TEXT NOT NULL,             -- 'Percentage Eaten', 'Fluid Volume', 'Weight'
    data_type       TEXT NOT NULL,             -- 'numeric' | 'text' | 'boolean'
    unit            TEXT,                      -- 'ml', 'kg', '%'
    min_value       NUMERIC,
    max_value       NUMERIC,
    is_required     BOOLEAN NOT NULL DEFAULT false,
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CHECK (data_type IN ('numeric', 'text', 'boolean'))
);

-- ---------------------------------------------------------------------
-- 13.2 Care events — the resident-scoped, floor-scoped recorded instances
-- ---------------------------------------------------------------------

CREATE TABLE care_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    floor_id        UUID REFERENCES floors(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    template_id     UUID NOT NULL REFERENCES care_templates(id),
    category_id     UUID NOT NULL REFERENCES care_categories(id),  -- denormalised from template for fast filtering
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'completed',  -- 'completed' | 'declined' | 'refused' | 'not_applicable'
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE care_event_options (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id            UUID NOT NULL REFERENCES care_homes(id),
    floor_id                UUID REFERENCES floors(id),
    care_event_id           UUID NOT NULL REFERENCES care_events(id),
    care_template_option_id UUID NOT NULL REFERENCES care_template_options(id),
    note                    TEXT,               -- e.g. reason, if this option requires_note
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (care_event_id, care_template_option_id)
);

CREATE TABLE care_event_measurements (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id                UUID NOT NULL REFERENCES care_homes(id),
    floor_id                    UUID REFERENCES floors(id),
    care_event_id                UUID NOT NULL REFERENCES care_events(id),
    care_template_measurement_id UUID NOT NULL REFERENCES care_template_measurements(id),
    value_numeric                NUMERIC,
    value_text                   TEXT,
    value_boolean                BOOLEAN,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (care_event_id, care_template_measurement_id)
);

CREATE TABLE care_event_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    floor_id        UUID REFERENCES floors(id),
    care_event_id   UUID NOT NULL REFERENCES care_events(id),
    file_url        TEXT NOT NULL,
    file_type       TEXT,               -- 'photo' | 'document'
    uploaded_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- 13.3 floor_id sync trigger on the resident-scoped event tables
--      (reuses sync_floor_id_from_resident() from migration 0013, which
--      reads NEW.resident_id — care_event_options/measurements/files
--      don't have resident_id directly, so they get a small dedicated
--      trigger that copies floor_id from their parent care_event instead)
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON care_events
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();

CREATE OR REPLACE FUNCTION sync_floor_id_from_care_event()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.floor_id IS NULL THEN
        SELECT floor_id INTO NEW.floor_id FROM care_events WHERE id = NEW.care_event_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON care_event_options
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_care_event();
CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON care_event_measurements
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_care_event();
CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON care_event_files
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_care_event();

-- ---------------------------------------------------------------------
-- 13.4 care_home_id sync for the template child tables (copy from parent
--      template/section, so a manager creating a home-specific template
--      doesn't have to repeat care_home_id on every option/measurement)
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION sync_care_home_id_from_template()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.care_home_id IS NULL AND TG_TABLE_NAME = 'care_template_sections' THEN
        SELECT care_home_id INTO NEW.care_home_id FROM care_templates WHERE id = NEW.template_id;
    ELSIF NEW.care_home_id IS NULL AND TG_TABLE_NAME = 'care_template_options' THEN
        SELECT ct.care_home_id INTO NEW.care_home_id
        FROM care_template_sections cts JOIN care_templates ct ON ct.id = cts.template_id
        WHERE cts.id = NEW.section_id;
    ELSIF NEW.care_home_id IS NULL AND TG_TABLE_NAME = 'care_template_measurements' THEN
        SELECT care_home_id INTO NEW.care_home_id FROM care_templates WHERE id = NEW.template_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_care_home_id BEFORE INSERT OR UPDATE ON care_template_sections
    FOR EACH ROW EXECUTE FUNCTION sync_care_home_id_from_template();
CREATE TRIGGER trg_sync_care_home_id BEFORE INSERT OR UPDATE ON care_template_options
    FOR EACH ROW EXECUTE FUNCTION sync_care_home_id_from_template();
CREATE TRIGGER trg_sync_care_home_id BEFORE INSERT OR UPDATE ON care_template_measurements
    FOR EACH ROW EXECUTE FUNCTION sync_care_home_id_from_template();

-- ---------------------------------------------------------------------
-- 13.5 updated_at triggers (mirrors migration 0011's generic pass, but
--      applied explicitly here since these are new tables added after it)
-- ---------------------------------------------------------------------

DO $$
DECLARE
    tbl TEXT;
    tables_with_updated_at TEXT[] := ARRAY[
        'care_categories', 'care_templates', 'care_template_sections',
        'care_template_options', 'care_template_measurements', 'care_events'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables_with_updated_at LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at();', tbl
        );
    END LOOP;
END $$;

-- ---------------------------------------------------------------------
-- 13.6 Row-Level Security
-- ---------------------------------------------------------------------

-- Template config tables: visible if global (care_home_id IS NULL) OR
-- belongs to the caller's own home. Written rows must belong to the
-- caller's home (you can't create a "global" template from a tenant session).
DO $$
DECLARE
    tbl TEXT;
    template_tables TEXT[] := ARRAY[
        'care_templates', 'care_template_sections', 'care_template_options',
        'care_template_measurements'
    ];
BEGIN
    FOREACH tbl IN ARRAY template_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);

        EXECUTE format($f$
            CREATE POLICY global_or_tenant_select ON %I
            FOR SELECT
            USING (
                care_home_id IS NULL
                OR care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
            );
        $f$, tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_write ON %I
            FOR INSERT
            WITH CHECK (
                care_home_id IS NULL
                OR care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
            );
        $f$, tbl);

        EXECUTE format($f$
            CREATE POLICY tenant_update ON %I
            FOR UPDATE
            USING (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid)
            WITH CHECK (care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid);
        $f$, tbl);
    END LOOP;
END $$;

-- care_categories: system-wide reference data (no care_home_id column at
-- all — it genuinely isn't tenant data, like an enum catalog). No RLS.

-- Resident-scoped event tables: full tenant + floor isolation, same
-- pattern as migration 0013's floor-scoped tables.
DO $$
DECLARE
    tbl TEXT;
    event_tables TEXT[] := ARRAY[
        'care_events', 'care_event_options', 'care_event_measurements', 'care_event_files'
    ];
BEGIN
    FOREACH tbl IN ARRAY event_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);

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

-- ---------------------------------------------------------------------
-- 13.7 Indexes for the query patterns this engine is built for:
--      "everything for this resident, this shift" and
--      "every event of this template, this period" (for AI summarisation)
-- ---------------------------------------------------------------------

CREATE INDEX idx_care_events_resident_time ON care_events (resident_id, occurred_at DESC);
CREATE INDEX idx_care_events_floor_time ON care_events (floor_id, occurred_at DESC);
CREATE INDEX idx_care_events_template_time ON care_events (template_id, occurred_at DESC);
CREATE INDEX idx_care_events_category_time ON care_events (category_id, occurred_at DESC);
CREATE INDEX idx_care_event_options_event ON care_event_options (care_event_id);
CREATE INDEX idx_care_event_measurements_event ON care_event_measurements (care_event_id);
CREATE INDEX idx_care_templates_category ON care_templates (category_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_template_sections_template ON care_template_sections (template_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_template_options_section ON care_template_options (section_id) WHERE deleted_at IS NULL;
""")


def downgrade() -> None:
    # Event tables first (they FK to the template tables and to each other)
    for tbl in ["care_event_files", "care_event_measurements", "care_event_options", "care_events"]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")

    # Template metadata tables, child-to-parent order
    for tbl in [
        "care_template_measurements", "care_template_options",
        "care_template_sections", "care_templates", "care_categories",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")

    # Functions introduced in this migration only (sync_floor_id_from_resident
    # belongs to migration 0013 and must not be touched here)
    op.execute("DROP FUNCTION IF EXISTS sync_floor_id_from_care_event();")
    op.execute("DROP FUNCTION IF EXISTS sync_care_home_id_from_template();")
