"""Storage for observations submitted through the generic API.

Historical domain records remain in their original tables and are read directly;
this migration deliberately does not copy or backfill them into observations.

Revision ID: 0030
Revises: 0029
"""

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE observation_type AS ENUM
            ('fluid_intake', 'weight', 'vitals', 'meal', 'mobility', 'note');
        CREATE TABLE observations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            care_home_id UUID NOT NULL REFERENCES care_homes(id),
            floor_id UUID NOT NULL REFERENCES floors(id),
            resident_id UUID NOT NULL REFERENCES residents(id),
            type observation_type NOT NULL,
            value JSONB NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            recorded_by UUID NOT NULL REFERENCES users(id),
            is_implausible BOOLEAN NOT NULL DEFAULT false,
            idempotency_key VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT observations_home_idempotency UNIQUE (care_home_id, idempotency_key)
        );
        CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON observations
            FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();
        CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON observations
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        ALTER TABLE observations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE observations FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_and_floor_isolation ON observations
            FOR ALL
            USING (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND floor_id = ANY (
                    string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
                )
            )
            WITH CHECK (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND floor_id = ANY (
                    string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
                )
                AND EXISTS (
                    SELECT 1 FROM residents r
                    WHERE r.id = observations.resident_id
                      AND r.care_home_id = observations.care_home_id
                      AND r.floor_id = observations.floor_id
                      AND r.deleted_at IS NULL
                )
            );
        CREATE INDEX ix_observations_resident_recorded_at ON observations (resident_id, recorded_at);
        CREATE INDEX ix_observations_care_home_type_recorded_at
            ON observations (care_home_id, type, recorded_at);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE observations;")
    op.execute("DROP TYPE observation_type;")
