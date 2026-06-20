"""public_sets surfaces early-access sets with data

Revision ID: 2d56f503f8c7
Revises: c3b31b58f8d0
Create Date: 2026-06-20 01:27:05.227273

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2d56f503f8c7'
down_revision: Union[str, None] = 'c3b31b58f8d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_sets AS
        SELECT
            s.code,
            s.name,
            s.start_date,
            s.end_date,
            (
                s.end_date IS NOT NULL
                AND now() >= ((s.start_date + time '12:00') AT TIME ZONE 'America/New_York')
                AND now() <  (((s.end_date + 1) + time '12:00') AT TIME ZONE 'America/New_York')
            ) AS is_active,
            (now() < ((s.start_date + time '12:00') AT TIME ZONE 'America/New_York')) AS early
        FROM sets s
        WHERE s.start_date <= CURRENT_DATE
           OR EXISTS (SELECT 1 FROM player_stats ps WHERE ps.set_id = s.id);
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_sets AS
        SELECT
            code,
            name,
            start_date,
            end_date,
            (
                end_date IS NOT NULL
                AND now() >= ((start_date + time '12:00') AT TIME ZONE 'America/New_York')
                AND now() <  (((end_date + 1) + time '12:00') AT TIME ZONE 'America/New_York')
            ) AS is_active
        FROM sets
        WHERE start_date <= CURRENT_DATE;
    """)
