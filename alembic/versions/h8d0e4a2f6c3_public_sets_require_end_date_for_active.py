"""Require end_date for is_active in public_sets

Perpetual sets like CUBE (no end_date) shouldn't be marked active even though
today is past their start_date. Active = today is inside [start_date, end_date]
AND end_date is set.

Revision ID: h8d0e4a2f6c3
Revises: g7c9d3f1e5b2
Create Date: 2026-05-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "h8d0e4a2f6c3"
down_revision: Union[str, None] = "g7c9d3f1e5b2"
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
            (end_date IS NOT NULL AND CURRENT_DATE BETWEEN start_date AND end_date) AS is_active
        FROM sets;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_sets AS
        SELECT
            code,
            name,
            start_date,
            end_date,
            (CURRENT_DATE BETWEEN start_date AND COALESCE(end_date, CURRENT_DATE)) AS is_active
        FROM sets;
    """)
