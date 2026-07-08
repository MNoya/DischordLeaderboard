"""Surface end_rank in the public per-event views

Adds the Arena rank at event completion (e.g. "Gold-3", "Mythic") to
public_player_draft_events and public_cube_season_events so the player profile
can show a rank icon per draft. NULL on the pod-draft arm — pods have no Arena rank.

Revision ID: a9r2k4e6n8d0
Revises: e2f4a6b8c1d3
Create Date: 2026-07-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a9r2k4e6n8d0"
down_revision: Union[str, None] = "e2f4a6b8c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_POD_SLUG_SQL = "trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g'))"


def _player_events_view_sql(end_rank_17l: str, end_rank_pod: str) -> str:
    return f"""
        CREATE OR REPLACE VIEW public_player_draft_events AS
        SELECT
            p.slug,
            s.code AS set_code,
            de.id AS event_id,
            de.format,
            de.expansion,
            de.wins,
            de.losses,
            de.is_trophy,
            de.colors,
            de.started_at,
            de.finished_at,
            de.seventeenlands_event_id,
            CASE
                WHEN de.seventeenlands_event_id IS NOT NULL
                    THEN 'https://www.17lands.com/deck/' || de.seventeenlands_event_id
                ELSE NULL
            END AS external_url,
            NULL::text AS event_name,
            NULL::text AS pod_event_slug{end_rank_17l}
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE p.active = true

        UNION ALL

        SELECT
            p.slug,
            pde.set_code,
            pdp.id AS event_id,
            'PodDraft' AS format,
            pde.set_code AS expansion,
            COALESCE(NULLIF(split_part(pdp.record, '-', 1), ''), '0')::int AS wins,
            COALESCE(NULLIF(split_part(pdp.record, '-', 2), ''), '0')::int AS losses,
            (pdp.placement = 1) AS is_trophy,
            COALESCE(pdp.deck_colors, '') AS colors,
            pde.event_time AS started_at,
            pde.event_time AS finished_at,
            NULL::text AS seventeenlands_event_id,
            pdp.draft_log_url AS external_url,
            pde.name AS event_name,
            {_POD_SLUG_SQL} AS pod_event_slug{end_rank_pod}
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND pdp.placement IS NOT NULL;
    """


_AVATAR_URL_SQL = """\
CASE WHEN b.avatar_hash IS NOT NULL AND b.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || b.discord_id || '/' || b.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


_BINNED_CTE = """\
seasons AS (
    SELECT
        code,
        start_date,
        LEAD(start_date) OVER (ORDER BY start_date) AS next_start
    FROM sets
    WHERE code <> 'CUBE'
),
cube_events AS (
    SELECT
        de.*,
        p.slug,
        p.display_name,
        p.avatar_hash,
        p.discord_id
    FROM draft_events de
    JOIN players p ON p.id = de.player_id
    JOIN sets s ON s.id = de.set_id
    WHERE s.code = 'CUBE' AND p.active = true AND de.started_at IS NOT NULL
),
marked AS (
    SELECT
        ce.*,
        CASE
            WHEN LAG(started_at) OVER w IS NULL
              OR started_at - LAG(started_at) OVER w > INTERVAL '7 days'
            THEN 1 ELSE 0
        END AS new_burst
    FROM cube_events ce
    WINDOW w AS (ORDER BY started_at)
),
bursts AS (
    SELECT
        m.*,
        SUM(new_burst) OVER (ORDER BY started_at ROWS UNBOUNDED PRECEDING) AS burst_id
    FROM marked m
),
anchored AS (
    SELECT
        br.*,
        MIN(started_at) OVER (PARTITION BY burst_id) AS burst_start
    FROM bursts br
),
binned AS (
    SELECT
        a.*,
        seasons.code AS season,
        'CUBE-' || seasons.code AS set_code
    FROM anchored a
    JOIN seasons
        ON a.burst_start::date >= seasons.start_date
       AND (seasons.next_start IS NULL OR a.burst_start::date < seasons.next_start)
)"""


def _cube_events_view_sql(end_rank: str) -> str:
    return f"""
        CREATE OR REPLACE VIEW public_cube_season_events AS
        WITH {_BINNED_CTE}
        SELECT
            b.slug,
            b.set_code,
            b.id AS event_id,
            b.format,
            b.expansion,
            b.wins,
            b.losses,
            b.is_trophy,
            b.colors,
            b.started_at,
            b.finished_at,
            b.seventeenlands_event_id,
            CASE
                WHEN b.seventeenlands_event_id IS NOT NULL
                    THEN 'https://www.17lands.com/deck/' || b.seventeenlands_event_id
                ELSE NULL
            END AS external_url,
            NULL::text AS event_name,
            NULL::text AS pod_event_slug,
            b.display_name,
            {_AVATAR_URL_SQL} AS avatar_url{end_rank}
        FROM binned b;
    """


def upgrade() -> None:
    op.execute(_player_events_view_sql(
        ",\n            de.end_rank",
        ",\n            NULL::text AS end_rank",
    ))
    op.execute(_cube_events_view_sql(",\n            b.end_rank"))
    for view in ("public_player_draft_events", "public_cube_season_events"):
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO anon;")
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO authenticated;")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS public_colors_summary;")
    op.execute("DROP VIEW IF EXISTS public_player_draft_events;")
    op.execute(_player_events_view_sql("", ""))
    op.execute("DROP VIEW IF EXISTS public_cube_season_events;")
    op.execute(_cube_events_view_sql(""))
    for view in ("public_player_draft_events", "public_cube_season_events"):
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO anon;")
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO authenticated;")
    op.execute(_COLORS_SUMMARY_MATVIEW_SQL)
    op.execute("CREATE UNIQUE INDEX public_colors_summary_pk ON public_colors_summary (set_code, colors);")
    op.execute("GRANT SELECT ON public_colors_summary TO anon;")
    op.execute("GRANT SELECT ON public_colors_summary TO authenticated;")


_COLORS_SUMMARY_MATVIEW_SQL = """
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
"""


def _grant_if_exists(view: str, statement: str) -> None:
    op.execute(f"""
        DO $$
        BEGIN
            IF to_regclass('public.{view}') IS NOT NULL THEN
                EXECUTE format('{statement}', '{view}');
            END IF;
        END
        $$;
    """)
