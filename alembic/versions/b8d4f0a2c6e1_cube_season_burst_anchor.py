"""Anchor cube seasons to the burst's start, not each event's date

A cube burst (a community cube run) can span a set rotation: the SOS run played
into June 23, the day MSH released, so 20 tail events binned into a phantom
CUBE-MSH season that then sorted newest and became the default cube board.

Bin every event by the set live when its *burst* began rather than when the
individual event was played. A burst is a run of cube activity with no >7-day
gap; all its events inherit the season of the set window holding the burst's
first event. A set only gets a season once a burst actually starts in its window
— a tail spilling past a rollover stays with the season it started in.

Revision ID: b8d4f0a2c6e1
Revises: a7c3f9e1b2d4
Create Date: 2026-06-26
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b8d4f0a2c6e1"
down_revision: Union[str, None] = "a7c3f9e1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN b.avatar_hash IS NOT NULL AND b.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || b.discord_id || '/' || b.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


_FORMAT_LABEL_CASE = """\
CASE
    WHEN b.format = 'PremierDraft' THEN 'Premier'
    WHEN b.format = 'TradDraft' THEN 'Trad'
    WHEN b.format IN (
        'Sealed',
        'TradSealed',
        'ArenaDirect_Sealed',
        'QualifierPlayInSealed',
        'QualifierPlayInTradSealed',
        'Qualifier_D1_Sealed',
        'Qualifier_D2_Sealed'
    ) THEN 'Sealed'
    WHEN b.format IN ('QuickDraft', 'PickTwoDraft', 'Emblem_QuickDraft') THEN 'Quick'
    WHEN b.format = 'LimitedChampionshipQualifier_Draft1' THEN 'LCQ Draft 1'
    WHEN b.format = 'LimitedChampionshipQualifier_Draft2' THEN 'LCQ Draft 2'
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


# The previous date-binned definitions, restored verbatim on downgrade.
_OLD_BINNED_CTE = """\
seasons AS (
    SELECT
        code,
        name,
        start_date,
        LEAD(start_date) OVER (ORDER BY start_date) AS next_start
    FROM sets
    WHERE code <> 'CUBE'
),
binned AS (
    SELECT
        de.*,
        p.slug,
        p.display_name,
        p.avatar_hash,
        p.discord_id,
        seasons.code AS season,
        'CUBE-' || seasons.code AS set_code
    FROM draft_events de
    JOIN players p ON p.id = de.player_id
    JOIN sets s ON s.id = de.set_id
    JOIN seasons
        ON de.started_at::date >= seasons.start_date
       AND (seasons.next_start IS NULL OR de.started_at::date < seasons.next_start)
    WHERE s.code = 'CUBE' AND p.active = true AND de.started_at IS NOT NULL
)"""


def upgrade() -> None:
    _create_views(_BINNED_CTE, burst_anchored=True)


def downgrade() -> None:
    _create_views(_OLD_BINNED_CTE, burst_anchored=False)


def _create_views(binned_cte: str, burst_anchored: bool) -> None:
    if burst_anchored:
        seasons_select = f"""
            CREATE OR REPLACE VIEW public_cube_seasons AS
            WITH {binned_cte}
            SELECT
                b.set_code,
                b.season AS label,
                s.name AS name,
                s.start_date,
                MIN(b.started_at)::date AS first_event,
                MAX(b.started_at)::date AS last_event,
                COUNT(*)::int AS events,
                COUNT(DISTINCT b.player_id)::int AS players
            FROM binned b
            JOIN sets s ON s.code = b.season
            GROUP BY b.set_code, b.season, s.name, s.start_date;
        """
    else:
        seasons_select = f"""
            CREATE OR REPLACE VIEW public_cube_seasons AS
            WITH {binned_cte},
            runs AS (
                SELECT
                    b.*,
                    (
                        LAG(b.started_at) OVER (ORDER BY b.started_at) IS NULL
                        OR b.started_at - LAG(b.started_at) OVER (ORDER BY b.started_at) > INTERVAL '7 days'
                    ) AS is_burst_start
                FROM binned b
            )
            SELECT
                r.set_code,
                r.season AS label,
                s.name AS name,
                s.start_date,
                (MIN(r.started_at) FILTER (WHERE r.is_burst_start))::date AS first_event,
                MAX(r.started_at)::date AS last_event,
                COUNT(*)::int AS events,
                COUNT(DISTINCT r.player_id)::int AS players
            FROM runs r
            JOIN sets s ON s.code = r.season
            GROUP BY r.set_code, r.season, s.name, s.start_date;
        """

    op.execute(seasons_select)

    op.execute(f"""
        CREATE OR REPLACE VIEW public_cube_season_breakdown AS
        WITH {binned_cte}
        SELECT
            b.set_code,
            b.slug,
            b.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            {_FORMAT_LABEL_CASE} AS format_label,
            COUNT(*)::int AS events,
            SUM(b.wins)::int AS wins,
            SUM(b.losses)::int AS losses,
            SUM(CASE WHEN b.is_trophy THEN 1 ELSE 0 END)::int AS trophies
        FROM binned b
        GROUP BY b.set_code, b.slug, b.display_name, {_AVATAR_URL_SQL}, {_FORMAT_LABEL_CASE}
        HAVING ({_FORMAT_LABEL_CASE}) IS NOT NULL;
    """)

    op.execute(f"""
        CREATE OR REPLACE VIEW public_cube_season_events AS
        WITH {binned_cte}
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
            {_AVATAR_URL_SQL} AS avatar_url
        FROM binned b;
    """)

    for view in ("public_cube_seasons", "public_cube_season_breakdown", "public_cube_season_events"):
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO anon;")
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO authenticated;")


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
