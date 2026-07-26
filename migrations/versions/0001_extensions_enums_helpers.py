"""extensions, helper functions, and enumerated types

Revision ID: 0001
Revises: None
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 0. EXTENSIONS & HELPER FUNCTIONS
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist; -- exclusion constraints on ranges (medication schedules)
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email columns

-- Generic updated_at maintenance
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- 1. ENUMERATED TYPES
-- =====================================================================

CREATE TYPE user_role AS ENUM ('carer', 'nurse', 'manager', 'family', 'emergency', 'system_admin');

CREATE TYPE consent_status AS ENUM ('granted', 'declined', 'withdrawn', 'pending');

CREATE TYPE care_plan_domain AS ENUM (
    'nutrition_hydration', 'continence', 'mobility', 'communication',
    'behaviour_wellbeing', 'skin_integrity', 'medication', 'sleep',
    'pain_management', 'social_activities', 'end_of_life'
);

CREATE TYPE care_plan_suggestion_status AS ENUM ('pending', 'approved', 'rejected', 'modified');

CREATE TYPE intake_method AS ENUM ('independent', 'assisted', 'fully_fed', 'pureed', 'thickened_fluids', 'peg_feed', 'refused');

CREATE TYPE meal_type AS ENUM ('breakfast', 'lunch', 'dinner', 'snack', 'supper', 'between_meal');

CREATE TYPE continence_product AS ENUM ('none', 'pad', 'pull_up', 'pad_and_pants', 'catheter', 'stoma');

CREATE TYPE continence_event_type AS ENUM ('continent', 'incontinent_urine', 'incontinent_faeces', 'incontinent_both', 'catheter_care', 'stoma_care');

CREATE TYPE bowel_type AS ENUM ('type_1', 'type_2', 'type_3', 'type_4', 'type_5', 'type_6', 'type_7'); -- Bristol Stool Chart

CREATE TYPE mobility_level AS ENUM ('independent', 'requires_supervision', 'requires_one_assist', 'requires_two_assist', 'hoist_dependent', 'bed_bound');

CREATE TYPE fall_severity AS ENUM ('no_injury', 'minor_injury', 'moderate_injury', 'major_injury', 'fatal');

CREATE TYPE communication_method AS ENUM ('verbal', 'non_verbal', 'sign', 'picture_cards', 'assistive_device', 'interpreter_required', 'written');

CREATE TYPE mood_state AS ENUM ('content', 'anxious', 'low', 'agitated', 'withdrawn', 'happy', 'distressed', 'settled');

CREATE TYPE behaviour_type AS ENUM (
    'verbal_aggression', 'physical_aggression', 'wandering', 'resistiveness_to_care',
    'repetitive_vocalisation', 'self_harm', 'sexually_inappropriate', 'other'
);

CREATE TYPE skin_risk_level AS ENUM ('low', 'medium', 'high', 'very_high'); -- e.g. Waterlow banding

CREATE TYPE wound_status AS ENUM ('new', 'improving', 'static', 'deteriorating', 'healed');

CREATE TYPE pain_scale_type AS ENUM ('self_report_0_10', 'abbey_pain_scale', 'faces_scale');

CREATE TYPE medication_route AS ENUM ('oral', 'topical', 'subcutaneous', 'intramuscular', 'inhaled', 'patch', 'peg', 'eye_drop', 'ear_drop', 'suppository', 'other');

CREATE TYPE medication_event_status AS ENUM ('administered', 'refused', 'omitted', 'not_available', 'self_administered', 'vomited_after');

CREATE TYPE incident_type AS ENUM ('fall', 'medication_error', 'behavioural', 'injury_unexplained', 'property_damage', 'near_miss', 'safeguarding', 'infection_control', 'other');

CREATE TYPE safeguarding_category AS ENUM ('physical_abuse', 'neglect', 'financial_abuse', 'psychological_abuse', 'sexual_abuse', 'discriminatory_abuse', 'self_neglect', 'organisational_abuse', 'other');

CREATE TYPE audit_action AS ENUM ('view', 'create', 'update', 'approve', 'export', 'emergency_access', 'login', 'login_failed');


-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP TYPE IF EXISTS audit_action;")
    op.execute("DROP TYPE IF EXISTS safeguarding_category;")
    op.execute("DROP TYPE IF EXISTS incident_type;")
    op.execute("DROP TYPE IF EXISTS medication_event_status;")
    op.execute("DROP TYPE IF EXISTS medication_route;")
    op.execute("DROP TYPE IF EXISTS pain_scale_type;")
    op.execute("DROP TYPE IF EXISTS wound_status;")
    op.execute("DROP TYPE IF EXISTS skin_risk_level;")
    op.execute("DROP TYPE IF EXISTS behaviour_type;")
    op.execute("DROP TYPE IF EXISTS mood_state;")
    op.execute("DROP TYPE IF EXISTS communication_method;")
    op.execute("DROP TYPE IF EXISTS fall_severity;")
    op.execute("DROP TYPE IF EXISTS mobility_level;")
    op.execute("DROP TYPE IF EXISTS bowel_type;")
    op.execute("DROP TYPE IF EXISTS continence_event_type;")
    op.execute("DROP TYPE IF EXISTS continence_product;")
    op.execute("DROP TYPE IF EXISTS meal_type;")
    op.execute("DROP TYPE IF EXISTS intake_method;")
    op.execute("DROP TYPE IF EXISTS care_plan_suggestion_status;")
    op.execute("DROP TYPE IF EXISTS care_plan_domain;")
    op.execute("DROP TYPE IF EXISTS consent_status;")
    op.execute("DROP TYPE IF EXISTS user_role;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
    op.execute("DROP EXTENSION IF EXISTS citext;")
    op.execute("DROP EXTENSION IF EXISTS btree_gist;")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
