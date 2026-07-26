"""medications, administration events, stock events

Revision ID: 0007
Revises: 0006
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 16. MEDICATIONS
-- =====================================================================

CREATE TABLE medications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    drug_name       TEXT NOT NULL,
    dose            TEXT NOT NULL,        -- '500mg', '10ml'
    route           medication_route NOT NULL,
    schedule_times  TIME[] NOT NULL DEFAULT '{}', -- e.g. {'08:00','20:00'}
    is_prn          BOOLEAN NOT NULL DEFAULT false,
    prn_max_per_day SMALLINT,
    prn_indication  TEXT,                 -- when to give: 'for pain', 'for agitation'
    prescriber      TEXT,
    start_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date        DATE,
    stock_count     INTEGER NOT NULL DEFAULT 0,
    stock_reorder_threshold INTEGER NOT NULL DEFAULT 7,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE medication_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    medication_id   UUID NOT NULL REFERENCES medications(id),
    resident_id     UUID NOT NULL REFERENCES residents(id),
    scheduled_for   TIMESTAMPTZ,          -- null for PRN doses
    administered_at TIMESTAMPTZ,
    status          medication_event_status NOT NULL,
    reason          TEXT,                 -- required when refused/omitted/not_available
    administered_by UUID REFERENCES users(id),
    witnessed_by    UUID REFERENCES users(id), -- controlled drugs often need 2 signatures
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE medication_stock_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id    UUID NOT NULL REFERENCES care_homes(id),
    medication_id   UUID NOT NULL REFERENCES medications(id),
    event_type      TEXT NOT NULL,        -- 'delivery', 'administered_decrement', 'wastage', 'count_correction'
    quantity_change INTEGER NOT NULL,     -- positive or negative
    recorded_by     UUID REFERENCES users(id),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =====================================================================
""")


def downgrade() -> None:

    op.execute("DROP TABLE IF EXISTS medication_stock_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS medication_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS medications CASCADE;")
