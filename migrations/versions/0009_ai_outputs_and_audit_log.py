"""AI output provenance and the append-only audit log

Revision ID: 0009
Revises: 0008
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 19. AI OUTPUTS (PROVENANCE) — every summary, flag, or answer
-- =====================================================================

CREATE TABLE ai_outputs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    output_type         TEXT NOT NULL,     -- 'daily_summary','shift_handover','risk_flag','family_digest','emergency_briefing','care_plan_suggestion'
    input_record_refs   JSONB NOT NULL DEFAULT '[]', -- [{"table":"food_intake_records","id":"..."}]
    prompt_template_version TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    output_text         TEXT NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    feedback_rating      SMALLINT CHECK (feedback_rating IN (-1, 0, 1)), -- 👎/none/👍
    feedback_comment      TEXT,
    feedback_by           UUID REFERENCES users(id),
    feedback_at            TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at             TIMESTAMPTZ
);


-- =====================================================================
-- 20. AUDIT LOG (APPEND-ONLY)
-- =====================================================================

CREATE TABLE audit_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    actor_id        UUID REFERENCES users(id),
    action          audit_action NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       UUID,
    justification   TEXT,               -- required for emergency_access
    ip_address      INET,
    device_info     TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Grants: application role gets INSERT + SELECT only (run once app_user role exists)
-- REVOKE UPDATE, DELETE ON audit_events FROM app_user;
-- GRANT INSERT, SELECT ON audit_events TO app_user;

CREATE OR REPLACE FUNCTION reject_audit_tamper()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_no_update
    BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_tamper();

CREATE TRIGGER trg_audit_no_delete
    BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_tamper();


-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP TRIGGER IF EXISTS trg_audit_no_delete ON audit_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_tamper();")
    op.execute("DROP TABLE IF EXISTS audit_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS ai_outputs CASCADE;")
