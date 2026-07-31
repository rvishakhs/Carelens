"""residents, contacts, consent

Revision ID: 0003
Revises: 0002
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 3. RESIDENTS: CORE RECORD, CONTACTS, CONSENT
-- =====================================================================

CREATE TABLE residents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    preferred_name      TEXT,                  -- what they like to be called
    date_of_birth       DATE NOT NULL,
    nhs_number          TEXT,                   -- encrypt at application layer
    gender              TEXT,
    room_number         TEXT,
    admission_date      DATE NOT NULL,
    discharge_date      DATE,
    status              TEXT NOT NULL DEFAULT 'active', -- active | discharged | deceased
    gp_practice_name    TEXT,
    gp_phone            TEXT,
    photo_url           TEXT,                   -- for staff recognition, not public
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

ALTER TABLE user_resident_links
    ADD CONSTRAINT fk_url_resident FOREIGN KEY (resident_id) REFERENCES residents(id);

CREATE TABLE resident_contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    full_name       TEXT NOT NULL,
    relationship    TEXT,
    is_next_of_kin  BOOLEAN NOT NULL DEFAULT false,
    is_emergency_contact BOOLEAN NOT NULL DEFAULT false,
    has_poa_health  BOOLEAN NOT NULL DEFAULT false, -- Power of Attorney: health & welfare
    has_poa_finance BOOLEAN NOT NULL DEFAULT false,
    phone           TEXT,
    email           CITEXT,
    address         TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE resident_consents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    resident_id         UUID NOT NULL REFERENCES residents(id),
    consent_type        TEXT NOT NULL,          -- 'data_processing', 'family_digest_access', 'photography', 'ai_summarisation'
    status               consent_status NOT NULL,
    consented_by         TEXT,                  -- resident / POA / best-interests decision
    capacity_assessed    BOOLEAN NOT NULL DEFAULT false,
    best_interests_note  TEXT,                  -- required if capacity_assessed = false and status = granted
    recorded_by          UUID REFERENCES users(id),
    valid_from           DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_to             DATE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at           TIMESTAMPTZ
);


-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP TABLE IF EXISTS resident_consents CASCADE;")
    op.execute("DROP TABLE IF EXISTS resident_contacts CASCADE;")
    op.execute("DROP TABLE IF EXISTS residents CASCADE;")
