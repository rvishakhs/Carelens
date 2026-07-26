"""care homes, users, family-resident links

Revision ID: 0002
Revises: 0001
Create Date: auto-generated from tested carelens-schema.sql

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
-- 2. TENANCY, IDENTITY & ACCESS
-- =====================================================================
CREATE TABLE care_homes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    cqc_location_id TEXT,                     -- CQC registration reference
    address_line1   TEXT,
    address_line2   TEXT,
    city            TEXT,
    postcode        TEXT,
    phone           TEXT,
    timezone        TEXT NOT NULL DEFAULT 'Europe/London',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id        UUID NOT NULL REFERENCES care_homes(id),
    oidc_subject        TEXT UNIQUE,           -- Keycloak/OIDC sub claim
    email               CITEXT,
    display_name        TEXT NOT NULL,
    role                user_role NOT NULL,
    mfa_enrolled        BOOLEAN NOT NULL DEFAULT false,
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

-- Family users are linked to specific residents they may view digests for
CREATE TABLE user_resident_links (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id  UUID NOT NULL REFERENCES care_homes(id),
    user_id       UUID NOT NULL REFERENCES users(id),
    resident_id   UUID NOT NULL,               -- FK added after residents table exists
    relationship  TEXT,                        -- 'daughter', 'son', 'POA', etc.
    granted_by    UUID REFERENCES users(id),    -- manager who authorised access
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ
);

-- =====================================================================
""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_resident_links CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS care_homes CASCADE;")
