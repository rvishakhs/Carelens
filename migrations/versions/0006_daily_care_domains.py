"""nutrition, continence, mobility, communication, behaviour/wellbeing, sleep, skin integrity, vitals, pain

Revision ID: 0006
Revises: 0005
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 7. NUTRITION & HYDRATION
-- ===================================================================== 

CREATE TABLE food_intake_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    meal_type       meal_type NOT NULL,
    percentage_eaten SMALLINT CHECK (percentage_eaten BETWEEN 0 AND 100),
    method          intake_method NOT NULL DEFAULT 'independent',
    texture_modified TEXT,             -- IDDSI level, e.g. 'Level 4 - Pureed'
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE fluid_intake_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    volume_ml       NUMERIC(6,1) NOT NULL CHECK (volume_ml >= 0),
    fluid_type      TEXT,              -- 'water', 'tea', 'thickened_juice', 'IV', etc.
    thickener_level TEXT,              -- IDDSI fluid level if applicable
    method          intake_method NOT NULL DEFAULT 'independent',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- Daily/weekly target vs actual, feeds deterioration detection directly
CREATE TABLE nutrition_hydration_targets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    daily_fluid_target_ml INTEGER,
    daily_calorie_target  INTEGER,
    set_by              UUID REFERENCES users(id),
    effective_from      DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to        DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

-- MUST (Malnutrition Universal Screening Tool) or similar
CREATE TABLE nutrition_risk_assessments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    assessment_tool     TEXT NOT NULL DEFAULT 'MUST',
    bmi_score           SMALLINT,
    weight_loss_score   SMALLINT,
    acute_disease_score SMALLINT,
    total_score         SMALLINT,
    risk_level          skin_risk_level,   -- reused enum: low/medium/high/very_high maps fine
    action_plan         TEXT,
    assessed_by         UUID REFERENCES users(id),
    assessed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_review_due     DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);


-- =====================================================================
-- 8. CONTINENCE & TOILETING
-- =====================================================================

CREATE TABLE continence_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    event_type      continence_event_type NOT NULL,
    product_used    continence_product,
    bowel_movement  BOOLEAN NOT NULL DEFAULT false,
    bristol_type    bowel_type,
    urine_output_ml NUMERIC(6,1),
    skin_condition  TEXT,               -- 'normal', 'sore', 'broken' — feeds skin integrity risk
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE continence_care_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    toileting_schedule  TEXT,           -- e.g. "prompted every 2 hours"
    product_regime      continence_product,
    bowel_management_plan TEXT,
    set_by              UUID REFERENCES users(id),
    effective_from      DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);


-- =====================================================================
-- 9. MOBILITY & FALLS
-- =====================================================================

CREATE TABLE mobility_assessments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    mobility_level      mobility_level NOT NULL,
    aids_used           TEXT[],          -- {'zimmer_frame','wheelchair','walking_stick'}
    transfer_method     TEXT,            -- 'standing hoist', 'sliding board', etc.
    falls_risk_score    SMALLINT,        -- e.g. FRAT / Morse Fall Scale total
    falls_risk_level    skin_risk_level, -- reused low/medium/high/very_high banding
    assessed_by         UUID REFERENCES users(id),
    assessed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_review_due     DATE,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

CREATE TABLE mobility_observations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    activity        TEXT NOT NULL,      -- 'walked to dining room', 'used wheelchair outdoors'
    distance_or_duration TEXT,
    assistance_given TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE falls_incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    occurred_at     TIMESTAMPTZ NOT NULL,
    location        TEXT,
    witnessed       BOOLEAN NOT NULL DEFAULT false,
    severity        fall_severity NOT NULL,
    injuries        TEXT,
    likely_cause    TEXT,
    action_taken    TEXT,               -- 'GP called', 'hospital admission', 'observations increased'
    post_fall_observations_required BOOLEAN NOT NULL DEFAULT true,
    reported_by     UUID REFERENCES users(id),
    family_informed BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
-- 10. COMMUNICATION
-- =====================================================================

CREATE TABLE communication_needs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    primary_method      communication_method NOT NULL,
    hearing_impairment   BOOLEAN NOT NULL DEFAULT false,
    hearing_aid_used     BOOLEAN NOT NULL DEFAULT false,
    visual_impairment    BOOLEAN NOT NULL DEFAULT false,
    glasses_used         BOOLEAN NOT NULL DEFAULT false,
    cognitive_considerations TEXT,       -- e.g. "responds best to short simple sentences"
    interpreter_language TEXT,
    aac_tools            TEXT,          -- augmentative & alternative communication tools used
    notes                TEXT,
    recorded_by          UUID REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at            TIMESTAMPTZ
);

CREATE TABLE communication_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    interaction_summary TEXT NOT NULL,   -- "expressed wish to call daughter", "declined to discuss meds"
    mood_during_interaction mood_state,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
-- 11. BEHAVIOUR & WELLBEING
-- =====================================================================

CREATE TABLE wellbeing_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    mood            mood_state NOT NULL,
    engagement_level SMALLINT CHECK (engagement_level BETWEEN 1 AND 5),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- ABC model: Antecedent, Behaviour, Consequence — standard behavioural charting
CREATE TABLE behaviour_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    behaviour_type  behaviour_type NOT NULL,
    antecedent      TEXT,               -- what happened immediately before
    behaviour_description TEXT NOT NULL,
    consequence     TEXT,               -- what happened/was done immediately after
    duration_minutes INTEGER,
    triggers_suspected TEXT,
    de_escalation_used TEXT,
    harm_to_self_or_others BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE mental_health_assessments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    assessment_tool TEXT NOT NULL,       -- 'Cornell Scale for Depression in Dementia', 'GDS', etc.
    total_score     SMALLINT,
    interpretation  TEXT,
    assessed_by     UUID REFERENCES users(id),
    assessed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_review_due DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
-- 12. SLEEP
-- =====================================================================

CREATE TABLE sleep_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    night_of        DATE NOT NULL,
    recorded_by     UUID REFERENCES users(id),
    settled_time    TIME,
    woke_time       TIME,
    night_wakings   SMALLINT NOT NULL DEFAULT 0,
    quality         TEXT,                -- 'good', 'restless', 'poor'
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (resident_id, night_of)
);


-- =====================================================================
-- 13. SKIN INTEGRITY & WOUNDS
-- =====================================================================

-- Waterlow (or Braden) pressure ulcer risk score
CREATE TABLE skin_integrity_assessments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    assessment_tool     TEXT NOT NULL DEFAULT 'Waterlow',
    total_score         SMALLINT,
    risk_level          skin_risk_level,
    pressure_areas_checked TEXT[],       -- {'sacrum','heels','elbows'}
    equipment_in_use    TEXT,            -- 'pressure-relieving mattress', 'heel protectors'
    reposition_frequency TEXT,           -- 'every 2 hours'
    assessed_by         UUID REFERENCES users(id),
    assessed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_review_due     DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

CREATE TABLE wound_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    body_location   TEXT NOT NULL,
    wound_type      TEXT,                -- 'pressure_ulcer', 'skin_tear', 'surgical'
    grade_or_category TEXT,              -- e.g. pressure ulcer category 1-4
    length_cm       NUMERIC(5,2),
    width_cm        NUMERIC(5,2),
    depth_cm        NUMERIC(5,2),
    status          wound_status NOT NULL DEFAULT 'new',
    treatment_plan  TEXT,
    photo_url       TEXT,
    first_observed  DATE NOT NULL DEFAULT CURRENT_DATE,
    healed_date     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE wound_review_notes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    wound_id        UUID NOT NULL REFERENCES wound_records(id),
    reviewed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_by     UUID REFERENCES users(id),
    status          wound_status NOT NULL,
    notes           TEXT,
    photo_url       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
-- 14. VITAL SIGNS & WEIGHT
-- =====================================================================

CREATE TABLE vital_signs_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by         UUID REFERENCES users(id),
    blood_pressure_systolic  SMALLINT,
    blood_pressure_diastolic SMALLINT,
    heart_rate_bpm       SMALLINT,
    respiratory_rate     SMALLINT,
    oxygen_saturation_pct SMALLINT CHECK (oxygen_saturation_pct BETWEEN 0 AND 100),
    temperature_celsius  NUMERIC(4,1),
    blood_glucose_mmol   NUMERIC(4,1),
    news2_score          SMALLINT,        -- National Early Warning Score 2, if computed
    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at            TIMESTAMPTZ
);

CREATE TABLE weight_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by     UUID REFERENCES users(id),
    weight_kg       NUMERIC(5,2) NOT NULL,
    height_cm       NUMERIC(5,1),
    bmi             NUMERIC(4,1) GENERATED ALWAYS AS (
                        CASE WHEN height_cm IS NOT NULL AND height_cm > 0
                             THEN ROUND((weight_kg / ((height_cm/100.0) ^ 2))::numeric, 1)
                             ELSE NULL END
                    ) STORED,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
-- 15. PAIN
-- =====================================================================

CREATE TABLE pain_assessments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    assessed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    assessed_by     UUID REFERENCES users(id),
    scale_type      pain_scale_type NOT NULL,
    score           SMALLINT NOT NULL,
    location        TEXT,
    pain_behaviours TEXT,             -- for non-verbal residents: grimacing, guarding, vocalising
    intervention    TEXT,             -- 'PRN analgesia given', 'repositioned'
    effective       BOOLEAN,          -- reviewed after intervention
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);


-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP TABLE IF EXISTS pain_assessments CASCADE;")
    op.execute("DROP TABLE IF EXISTS weight_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS vital_signs_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS wound_review_notes CASCADE;")
    op.execute("DROP TABLE IF EXISTS wound_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS skin_integrity_assessments CASCADE;")
    op.execute("DROP TABLE IF EXISTS sleep_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS mental_health_assessments CASCADE;")
    op.execute("DROP TABLE IF EXISTS behaviour_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS wellbeing_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS communication_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS communication_needs CASCADE;")
    op.execute("DROP TABLE IF EXISTS falls_incidents CASCADE;")
    op.execute("DROP TABLE IF EXISTS mobility_observations CASCADE;")
    op.execute("DROP TABLE IF EXISTS mobility_assessments CASCADE;")
    op.execute("DROP TABLE IF EXISTS continence_care_plans CASCADE;")
    op.execute("DROP TABLE IF EXISTS continence_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS nutrition_risk_assessments CASCADE;")
    op.execute("DROP TABLE IF EXISTS nutrition_hydration_targets CASCADE;")
    op.execute("DROP TABLE IF EXISTS fluid_intake_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS food_intake_records CASCADE;")
