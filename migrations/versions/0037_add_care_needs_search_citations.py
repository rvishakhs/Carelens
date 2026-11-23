"""Allow care-needs records to be persisted as resident-search citations.

Revision ID: 0037
Revises: 0036
"""

from alembic import op


revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

_CONSTRAINT = "ck_resident_history_search_citation_source_type"
_SOURCES = (
    "'fall', 'incident', 'observation', 'care_event', 'appointment', 'care_plan', "
    "'mobility_assessment', 'nutrition_assessment', 'skin_assessment', 'mental_health_assessment', "
    "'sleep', 'nutrition', 'mobility', 'wellbeing', 'communication', 'wound', "
    "'communication_need', 'nutrition_target', 'continence_care_plan'"
)
_PREVIOUS_SOURCES = (
    "'fall', 'incident', 'observation', 'care_event', 'appointment', 'care_plan', "
    "'mobility_assessment', 'nutrition_assessment', 'skin_assessment', 'mental_health_assessment', "
    "'sleep', 'nutrition', 'mobility', 'wellbeing', 'communication', 'wound'"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE resident_history_search_citations DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute(f"ALTER TABLE resident_history_search_citations ADD CONSTRAINT {_CONSTRAINT} CHECK (source_type IN ({_SOURCES}))")


def downgrade() -> None:
    op.execute(f"ALTER TABLE resident_history_search_citations DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute(f"ALTER TABLE resident_history_search_citations ADD CONSTRAINT {_CONSTRAINT} CHECK (source_type IN ({_PREVIOUS_SOURCES}))")
