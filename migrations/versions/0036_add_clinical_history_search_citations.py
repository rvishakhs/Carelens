"""Allow clinical-history citations and preserve date-only source precision.

Revision ID: 0036
Revises: 0035
"""

from alembic import op


revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


_CONSTRAINT = "ck_resident_history_search_citation_source_type"
_SOURCES = (
    "'fall', 'incident', 'observation', 'care_event', 'appointment', 'care_plan', "
    "'mobility_assessment', 'nutrition_assessment', 'skin_assessment', 'mental_health_assessment', "
    "'sleep', 'nutrition', 'mobility', 'wellbeing', 'communication', 'wound'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE resident_history_search_citations ALTER COLUMN occurred_at DROP NOT NULL")
    op.execute("ALTER TABLE resident_history_search_citations ADD COLUMN time_precision TEXT NOT NULL DEFAULT 'timestamp'")
    op.execute("ALTER TABLE resident_history_search_citations ADD COLUMN source_date DATE")
    op.execute(f"ALTER TABLE resident_history_search_citations DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE resident_history_search_citations ADD CONSTRAINT {_CONSTRAINT} "
        f"CHECK (source_type IN ({_SOURCES}))"
    )
    op.execute(
        "ALTER TABLE resident_history_search_citations ADD CONSTRAINT "
        "ck_resident_history_search_citation_time_precision "
        "CHECK ((time_precision = 'timestamp' AND occurred_at IS NOT NULL AND source_date IS NULL) "
        "OR (time_precision = 'date' AND occurred_at IS NULL AND source_date IS NOT NULL))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE resident_history_search_citations DROP CONSTRAINT IF EXISTS ck_resident_history_search_citation_time_precision")
    op.execute(f"ALTER TABLE resident_history_search_citations DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute("ALTER TABLE resident_history_search_citations ADD CONSTRAINT ck_resident_history_search_citation_source_type CHECK (source_type IN ('fall', 'incident', 'observation', 'care_event', 'appointment', 'care_plan', 'mobility_assessment', 'nutrition_assessment', 'skin_assessment', 'mental_health_assessment'))")
    op.execute("ALTER TABLE resident_history_search_citations DROP COLUMN source_date")
    op.execute("ALTER TABLE resident_history_search_citations DROP COLUMN time_precision")
    op.execute("ALTER TABLE resident_history_search_citations ALTER COLUMN occurred_at SET NOT NULL")
