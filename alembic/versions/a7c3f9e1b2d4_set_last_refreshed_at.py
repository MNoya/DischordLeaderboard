"""Track full-refresh tick time per set

Revision ID: a7c3f9e1b2d4
Revises: c4d5e6f7a8b9
Create Date: 2026-06-26

The leaderboard "last updated" derived from MAX(player_stats.last_fetched_at), which a single
join/relink bumps to now even though the board as a whole wasn't refreshed. sets.last_refreshed_at
records when the full active-player refresh last completed; only the tick and !refresh write it.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7c3f9e1b2d4"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sets", sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True))
    # A closed set is only refreshed up to the day it rotated out; later per-player joins
    # re-pull its history but don't constitute a board refresh, so seed inactive sets from
    # end_date (noon ET, matching the public_sets active window) rather than max fetch time.
    op.execute("""
        UPDATE sets s
        SET last_refreshed_at = CASE
            WHEN s.end_date IS NULL OR s.end_date >= CURRENT_DATE
                THEN (SELECT max(ps.last_fetched_at) FROM player_stats ps WHERE ps.set_id = s.id)
            ELSE ((s.end_date + 1 + time '12:00') AT TIME ZONE 'America/New_York')
        END;
    """)
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
            (now() < ((s.start_date + time '12:00') AT TIME ZONE 'America/New_York')) AS early,
            s.last_refreshed_at
        FROM sets s
        WHERE s.start_date <= CURRENT_DATE
           OR EXISTS (SELECT 1 FROM player_stats ps WHERE ps.set_id = s.id);
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_sets;")
    op.execute("""
        CREATE VIEW public_sets AS
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
    for role in ("anon", "authenticated"):
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                    GRANT SELECT ON public.public_sets TO {role};
                END IF;
            END
            $$;
        """)
    op.drop_column("sets", "last_refreshed_at")
