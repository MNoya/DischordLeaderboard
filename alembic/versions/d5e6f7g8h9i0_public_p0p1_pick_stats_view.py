"""Add public_p0p1_pick_stats view

Revision ID: d5e6f7g8h9i0
Revises: ep1s0des7feed
Create Date: 2026-06-17

Aggregate pick counts per (set_code, slot, card_name) for the P0P1 contest.
Hidden until MSH voting deadline via WHERE now() > timestamp. View bypasses
RLS (runs as owner), same pattern as public_leaderboard.

Rebased onto ep1s0des7feed (was c3d4e5f6g7h8): this and the p0p1 pick-stats
migrations after it never ran anywhere outside this branch, so rebasing
past master's pod-draft-log/CUBE/episodes chain keeps a single linear
history instead of an extra merge-revision node.
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
