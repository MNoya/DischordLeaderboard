"""Add public_p0p1_pick_stats view

Revision ID: d5e6f7g8h9i0
Revises: ep1s0des7feed
Create Date: 2026-06-17

Aggregate pick counts per (set_code, slot, card_name) for the P0P1 contest.
Hidden until MSH voting deadline via WHERE now() > timestamp. View bypasses
RLS (runs as owner), same pattern as public_leaderboard.

Only counts players who filled every slot for the set, so every slot in a
given set shares one consistent vote total (and pick_pct denominator) -
partial entries from players who never finished don't get counted.

Rebased onto ep1s0des7feed (was c3d4e5f6g7h8) after merging master in,
to keep a single linear history instead of an extra merge-revision node.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d5e6f7g8h9i0"
down_revision: Union[str, None] = "ep1s0des7feed"
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
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                GRANT SELECT ON public_p0p1_pick_stats TO anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                GRANT SELECT ON public_p0p1_pick_stats TO authenticated;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_p0p1_pick_stats;")
