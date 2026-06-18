"""Restrict public_p0p1_pick_stats to complete entries

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
Create Date: 2026-06-19

Previously every row in p0p1_entries counted, including partial entries
from players who never finished all slots, so each slot's vote total
(and therefore pick_pct's denominator) could differ slot to slot. Only
count players who filled every slot for the set, so every slot in a
given set shares one consistent total.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e6f7g8h9i0j1"
down_revision: Union[str, None] = "d5e6f7g8h9i0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_p0p1_pick_stats AS
        WITH slot_counts AS (
            SELECT set_code, COUNT(DISTINCT slot) AS total_slots
            FROM p0p1_entries
            GROUP BY set_code
        ),
        complete_entrants AS (
            SELECT e.user_id, e.set_code
            FROM p0p1_entries e
            JOIN slot_counts s USING (set_code)
            GROUP BY e.user_id, e.set_code, s.total_slots
            HAVING COUNT(*) = s.total_slots
        )
        SELECT
            e.set_code,
            e.slot,
            e.card_name,
            COUNT(*)::int AS pick_count,
            ROUND(COUNT(*)::numeric * 100.0 /
                NULLIF(SUM(COUNT(*)) OVER (PARTITION BY e.set_code, e.slot), 0), 1
            ) AS pick_pct
        FROM p0p1_entries e
        JOIN complete_entrants c USING (user_id, set_code)
        WHERE now() > '2026-06-23T15:00:00Z'
        GROUP BY e.set_code, e.slot, e.card_name;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_p0p1_pick_stats AS
        SELECT
            set_code,
            slot,
            card_name,
            COUNT(*)::int AS pick_count,
            ROUND(COUNT(*)::numeric * 100.0 /
                NULLIF(SUM(COUNT(*)) OVER (PARTITION BY set_code, slot), 0), 1
            ) AS pick_pct
        FROM p0p1_entries
        WHERE now() > '2026-06-23T15:00:00Z'
        GROUP BY set_code, slot, card_name;
    """)
