"""public_sets active at noon ET release

Revision ID: c3b31b58f8d0
Revises: d5e6f7g8h9i0
Create Date: 2026-06-20 00:22:22.424035

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3b31b58f8d0'
down_revision: Union[str, None] = 'd5e6f7g8h9i0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_sets AS
        SELECT
            code,
            name,
            start_date,
            end_date,
            (end_date IS NOT NULL AND CURRENT_DATE BETWEEN start_date AND end_date) AS is_active
        FROM sets
        WHERE start_date <= CURRENT_DATE;
    """)
