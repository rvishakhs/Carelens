"""Handover jobs, dispatch outbox, evidence manifests and immutable draft versions.

Revision ID: 0001_handover
Revises: None
"""

from alembic import op

revision = "0001_handover"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE handover_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    resident_id UUID NOT NULL,
    shift_start TIMESTAMPTZ NOT NULL,
    shift_end TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL,
    generation_number INTEGER NOT NULL DEFAULT 1 CHECK (generation_number > 0),
    previous_job_id UUID,
    idempotency_key VARCHAR(255) NOT NULL CHECK (length(idempotency_key) > 0),
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual', 'scheduled')),
    requested_by UUID,
    service_identity TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'handover_generation'
        CHECK (purpose = 'handover_generation'),
    state TEXT NOT NULL DEFAULT 'queued'
        CHECK (state IN ('queued', 'running', 'draft_ready', 'failed', 'cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    failure_code VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    CHECK (shift_end > shift_start),
    CHECK (length(timezone) > 0 AND length(service_identity) > 0),
    CHECK (trigger_type <> 'manual' OR requested_by IS NOT NULL),
    CHECK ((state = 'running') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CHECK ((lease_token IS NULL) = (lease_expires_at IS NULL)),
    CHECK ((state IN ('draft_ready', 'failed', 'cancelled')) = (completed_at IS NOT NULL)),
    CHECK ((generation_number = 1 AND previous_job_id IS NULL)
        OR (generation_number > 1 AND previous_job_id IS NOT NULL)),
    CHECK (previous_job_id IS NULL OR previous_job_id <> id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, resident_id, id),
    UNIQUE (tenant_id, resident_id, shift_start, shift_end, id),
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (tenant_id, resident_id, shift_start, shift_end, generation_number),
    FOREIGN KEY (tenant_id, resident_id, shift_start, shift_end, previous_job_id)
        REFERENCES handover_jobs (tenant_id, resident_id, shift_start, shift_end, id)
);
CREATE INDEX ix_handover_jobs_dispatch ON handover_jobs (tenant_id, state, next_attempt_at);
CREATE INDEX ix_handover_jobs_lease ON handover_jobs (tenant_id, lease_expires_at)
    WHERE state = 'running';
CREATE INDEX ix_handover_jobs_resident ON handover_jobs (tenant_id, resident_id, shift_end DESC);

CREATE TABLE dispatch_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    job_id UUID NOT NULL,
    dispatch_number INTEGER NOT NULL DEFAULT 1 CHECK (dispatch_number > 0),
    task_name TEXT NOT NULL DEFAULT 'intelligence.handover.generate'
        CHECK (task_name = 'intelligence.handover.generate'),
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'publishing', 'published')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    failure_code VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((state = 'publishing') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CHECK ((lease_token IS NULL) = (lease_expires_at IS NULL)),
    CHECK ((state = 'published') = (published_at IS NOT NULL)),
    UNIQUE (tenant_id, job_id, dispatch_number),
    FOREIGN KEY (tenant_id, job_id) REFERENCES handover_jobs (tenant_id, id)
);
CREATE INDEX ix_dispatch_outbox_due ON dispatch_outbox (tenant_id, state, available_at);

CREATE TABLE evidence_manifests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    resident_id UUID NOT NULL,
    job_id UUID NOT NULL,
    attempt_token UUID NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    evidence_cutoff TIMESTAMPTZ,
    coverage_complete BOOLEAN NOT NULL,
    source_checkpoint JSONB,
    sources JSONB NOT NULL CHECK (jsonb_typeof(sources) = 'array'),
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(warnings) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, resident_id, job_id, id),
    UNIQUE (tenant_id, job_id, attempt_token),
    FOREIGN KEY (tenant_id, resident_id, job_id)
        REFERENCES handover_jobs (tenant_id, resident_id, id)
);
CREATE INDEX ix_evidence_manifests_job ON evidence_manifests (tenant_id, job_id);

CREATE TABLE handover_draft_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    resident_id UUID NOT NULL,
    job_id UUID NOT NULL,
    manifest_id UUID NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    version_kind TEXT NOT NULL CHECK (version_kind IN ('ai_original', 'staff_revision')),
    previous_version_id UUID,
    authored_by UUID,
    sections JSONB NOT NULL CHECK (jsonb_typeof(sections) = 'array'),
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(warnings) = 'array'),
    agent_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    gateway_version TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_version TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((version_kind = 'ai_original' AND version_number = 1 AND previous_version_id IS NULL)
        OR (version_kind = 'staff_revision' AND version_number > 1
            AND previous_version_id IS NOT NULL AND authored_by IS NOT NULL)),
    CHECK (previous_version_id IS NULL OR previous_version_id <> id),
    UNIQUE (tenant_id, job_id, id),
    UNIQUE (tenant_id, job_id, version_number),
    FOREIGN KEY (tenant_id, resident_id, job_id, manifest_id)
        REFERENCES evidence_manifests (tenant_id, resident_id, job_id, id),
    FOREIGN KEY (tenant_id, job_id, previous_version_id)
        REFERENCES handover_draft_versions (tenant_id, job_id, id)
);
CREATE UNIQUE INDEX uq_handover_original ON handover_draft_versions (tenant_id, job_id)
    WHERE version_kind = 'ai_original';

CREATE FUNCTION intelligence_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER handover_jobs_updated BEFORE UPDATE ON handover_jobs
    FOR EACH ROW EXECUTE FUNCTION intelligence_touch_updated_at();
CREATE TRIGGER dispatch_outbox_updated BEFORE UPDATE ON dispatch_outbox
    FOR EACH ROW EXECUTE FUNCTION intelligence_touch_updated_at();

CREATE FUNCTION intelligence_reject_evidence_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Evidence and draft versions are immutable; insert a new version';
END;
$$;
CREATE TRIGGER evidence_manifest_immutable BEFORE UPDATE ON evidence_manifests
    FOR EACH ROW EXECUTE FUNCTION intelligence_reject_evidence_update();
CREATE TRIGGER handover_draft_immutable BEFORE UPDATE ON handover_draft_versions
    FOR EACH ROW EXECUTE FUNCTION intelligence_reject_evidence_update();
""")
    for table in ("handover_jobs", "dispatch_outbox", "evidence_manifests", "handover_draft_versions"):
        # Identifiers are internal constants, not request input.
        op.execute(f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON {table}
    USING (tenant_id = NULLIF(current_setting('intelligence.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('intelligence.tenant_id', true), '')::uuid);
REVOKE ALL ON {table} FROM PUBLIC;
REVOKE ALL ON {table} FROM intelligence_app;
GRANT SELECT, INSERT ON {table} TO intelligence_app;
""")
    op.execute("""
GRANT UPDATE ON handover_jobs, dispatch_outbox TO intelligence_app;
REVOKE ALL ON FUNCTION intelligence_touch_updated_at() FROM PUBLIC;
REVOKE ALL ON FUNCTION intelligence_reject_evidence_update() FROM PUBLIC;
REVOKE ALL ON alembic_version FROM intelligence_app;
""")


def downgrade() -> None:
    op.execute("""
DROP TABLE handover_draft_versions;
DROP TABLE evidence_manifests;
DROP TABLE dispatch_outbox;
DROP TABLE handover_jobs;
DROP FUNCTION intelligence_reject_evidence_update();
DROP FUNCTION intelligence_touch_updated_at();
""")
