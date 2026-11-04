"""Store opaque composite source revisions without losing legacy timestamps.

Revision ID: 0034
Revises: 0033
"""

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use the same UTC ISO representation as revision_token(), independent of
    # the connection's timezone. NULL remains NULL.
    op.execute("""
        ALTER TABLE resident_history_search_citations
        ALTER COLUMN source_version TYPE TEXT USING (
            to_char(source_version AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '+00:00'
        )
    """)


def downgrade() -> None:
    # Composite hashes cannot be cast back to timestamps. Refuse rather than
    # discard citation provenance or delete saved searches on downgrade.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM resident_history_search_citations
                WHERE source_version IS NOT NULL
                  AND source_version !~ '^\\d{4}-\\d{2}-\\d{2}T'
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade citation revisions while opaque tokens exist';
            END IF;
        END $$;
    """)
    op.execute("""
        ALTER TABLE resident_history_search_citations
        ALTER COLUMN source_version TYPE TIMESTAMPTZ USING source_version::timestamptz
    """)
