"""Materialize per-color archetype tallies for the leaderboard sidebar

The Top Colors sidebar used to download every draft event of the active set and
tally per-color trophies/events/players in the browser — a ~10K-row sequential
scan on each page load, the heaviest read on the nano-tier database. This pushes
the GROUP BY into Postgres as a materialized view that returns ~20 rows.

Each event lands in two overlapping buckets, matching the boards' filters: its
main-color archetype (splashes dropped, WUBRG-sorted) and, when it qualifies as
Soup, the cross-cutting MULTI bucket. Soup is 4+ effective colors, raised to 3+
main colors for cube where splashing is cheaper — mirroring isSoup in the
frontend. Pod rows carry empty colors and fall out of both buckets.

The matview unions the lifetime event view (every regular set plus bare CUBE)
with the windowed cube-season events, so it answers by set_code alone. The bot
refreshes it on each refresh tick (refresh_colors_summary).

Revision ID: c5d9f1a3b7e2
Revises: b8d4f0a2c6e1
Create Date: 2026-06-26
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c5d9f1a3b7e2"
down_revision: Union[str, None] = "b8d4f0a2c6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW public_colors_summary AS
        WITH events AS (
            SELECT set_code, slug, COALESCE(colors, '') AS colors, is_trophy, (set_code = 'CUBE') AS is_cube
            FROM public_player_draft_events
            UNION ALL
            SELECT set_code, slug, COALESCE(colors, '') AS colors, is_trophy, true AS is_cube
            FROM public_cube_season_events
        ),
        classified AS (
            SELECT
                e.set_code,
                e.slug,
                e.is_trophy,
                e.is_cube,
                (CASE WHEN x.main LIKE '%W%' THEN 'W' ELSE '' END) ||
                (CASE WHEN x.main LIKE '%U%' THEN 'U' ELSE '' END) ||
                (CASE WHEN x.main LIKE '%B%' THEN 'B' ELSE '' END) ||
                (CASE WHEN x.main LIKE '%R%' THEN 'R' ELSE '' END) ||
                (CASE WHEN x.main LIKE '%G%' THEN 'G' ELSE '' END) AS main_colors,
                (CASE WHEN x.all_colors LIKE '%W%' THEN 1 ELSE 0 END) +
                (CASE WHEN x.all_colors LIKE '%U%' THEN 1 ELSE 0 END) +
                (CASE WHEN x.all_colors LIKE '%B%' THEN 1 ELSE 0 END) +
                (CASE WHEN x.all_colors LIKE '%R%' THEN 1 ELSE 0 END) +
                (CASE WHEN x.all_colors LIKE '%G%' THEN 1 ELSE 0 END) AS effective_color_count
            FROM events e,
            LATERAL (SELECT regexp_replace(e.colors, '[a-z]', '', 'g') AS main, upper(e.colors) AS all_colors) x
        ),
        tagged AS (
            SELECT set_code, slug, is_trophy, main_colors AS colors
            FROM classified
            WHERE main_colors <> ''
            UNION ALL
            SELECT set_code, slug, is_trophy, 'MULTI' AS colors
            FROM classified
            WHERE effective_color_count >= 4 AND (NOT is_cube OR length(main_colors) >= 3)
        )
        SELECT
            set_code,
            colors,
            SUM(CASE WHEN is_trophy THEN 1 ELSE 0 END)::int AS trophies,
            COUNT(*)::int AS events,
            COUNT(DISTINCT slug)::int AS players
        FROM tagged
        GROUP BY set_code, colors;
    """)
    op.execute("CREATE UNIQUE INDEX public_colors_summary_pk ON public_colors_summary (set_code, colors);")
    op.execute("GRANT SELECT ON public_colors_summary TO anon;")
    op.execute("GRANT SELECT ON public_colors_summary TO authenticated;")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS public_colors_summary;")
