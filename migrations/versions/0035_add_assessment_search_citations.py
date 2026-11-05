"""Allow concrete formal-assessment sources in resident-search citations.

Revision ID: 0035
Revises: 0034
"""

from alembic import op


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


_CONSTRAINT = "ck_resident_history_search_citation_source_type"
_LEGACY_CONSTRAINT = "resident_history_search_citations_source_type_check"
_SOURCES = (
    "'fall', 'incident', 'observation', 'care_event', 'appointment', 'care_plan', "
    "'mobility_assessment', 'nutrition_assessment', 'skin_assessment', 'mental_health_assessment'"
)
_LEGACY_SOURCES = "'fall', 'incident', 'observation', 'care_event', 'appointment', 'care_plan'"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE resident_history_search_citations "
        f"DROP CONSTRAINT IF EXISTS {_LEGACY_CONSTRAINT}"
    )
    op.execute(
        f"ALTER TABLE resident_history_search_citations "
        f"ADD CONSTRAINT {_CONSTRAINT} CHECK (source_type IN ({_SOURCES}))"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE resident_history_search_citations "
        f"DROP CONSTRAINT IF EXISTS {_CONSTRAINT}"
    )
    op.execute(
        f"ALTER TABLE resident_history_search_citations "
        f"ADD CONSTRAINT {_CONSTRAINT} CHECK (source_type IN ({_LEGACY_SOURCES}))"
    )
