"""alter residents status

Revision ID: 349b7e36f226
Revises: 0011
Create Date: 2026-07-26 23:19:08.361090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '349b7e36f226'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
            CREATE TYPE resident_status AS ENUM (
                'Active',
                'Discharged',
                'Hospitalized',
                'Archived'
            );
        """)

    # Remove the existing default
    op.execute("""
               ALTER TABLE residents
                   ALTER COLUMN status DROP DEFAULT;
               """)

    # Convert TEXT -> ENUM
    op.execute("""
               ALTER TABLE residents
               ALTER
               COLUMN status
            TYPE resident_status
            USING status::resident_status;
               """)

    # Set the new default
    op.execute("""
               ALTER TABLE residents
                   ALTER COLUMN status
                       SET DEFAULT 'active';
               """)


def downgrade() -> None:
    # Remove the enum default
    op.execute("""
        ALTER TABLE residents
        ALTER COLUMN status DROP DEFAULT;
    """)

    # Convert ENUM -> TEXT
    op.execute("""
        ALTER TABLE residents
        ALTER COLUMN status
        TYPE TEXT
        USING status::TEXT;
    """)

    # Restore text default
    op.execute("""
        ALTER TABLE residents
        ALTER COLUMN status
        SET DEFAULT 'active';
    """)

    # Drop the enum type
    op.execute("""
        DROP TYPE resident_status;
    """)