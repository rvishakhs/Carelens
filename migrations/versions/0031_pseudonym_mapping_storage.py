"""Complete the existing summary gateway's missing mapping storage.

Revision ID: 0031
Revises: 0030
"""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE pseudonym_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            care_home_id UUID NOT NULL REFERENCES care_homes(id),
            resident_id UUID NOT NULL REFERENCES residents(id),
            token VARCHAR(32) NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT uq_pseudonym_mapping_resident UNIQUE (care_home_id, resident_id)
        );
        CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON pseudonym_mappings
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        ALTER TABLE pseudonym_mappings ENABLE ROW LEVEL SECURITY;
        ALTER TABLE pseudonym_mappings FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_and_resident_isolation ON pseudonym_mappings
            FOR ALL
            USING (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1 FROM residents r
                    WHERE r.id = pseudonym_mappings.resident_id
                      AND r.care_home_id = pseudonym_mappings.care_home_id
                      AND r.deleted_at IS NULL
                )
            )
            WITH CHECK (
                care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1 FROM residents r
                    WHERE r.id = pseudonym_mappings.resident_id
                      AND r.care_home_id = pseudonym_mappings.care_home_id
                      AND r.deleted_at IS NULL
                )
            );
        CREATE INDEX ix_pseudonym_mappings_resident_id ON pseudonym_mappings (resident_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE pseudonym_mappings;")
