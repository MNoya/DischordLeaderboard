"""Cube season views: per-set-window leaderboards exposed as virtual set codes

CUBE recurs every set, so a "season" is the cube drafts played during a regular
set's active window. Each season surfaces as a synthetic ``set_code`` of the form
``CUBE-<SET>`` (e.g. ``CUBE-SOS``) so the frontend reaches it through the same
set-code-keyed paths and fetchers as any other board — bare ``CUBE`` stays the
lifetime board (and keeps pods); the season codes are 17lands-cube only.

The window is contiguous [start_date, next regular set's start_date) — derived
from the sets table rather than each set's stored end_date, which leaves gaps
when CUBE was interleaved into the rotation. Drafts are binned by ``started_at``
(the set live when the draft began).

  public_cube_seasons          — one row per season window that contains cube drafts
  public_cube_season_breakdown — per-(season, player, format) aggregates; the frontend
                                 scores these with scoreFromGroups like the lifetime board
  public_cube_season_events    — per-event rows mirroring public_player_draft_events,
                                 so color/trophy boards work by set_code alone

Revision ID: c1u2b3e4s5n6
Revises: e5f6g7h8i9j0
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c1u2b3e4s5n6"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
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
    # Cube comes and goes in bursts that don't align with set releases; a burst can spill a stray
    # event across a rollover. first_event is the start of the first burst that *begins* inside the
    # window (a burst start = no cube activity in the prior 7 days), so a tail from the previous
    # burst doesn't masquerade as the season's start. last_event is the latest cube event in the window.
    op.execute(f"""
        CREATE OR REPLACE VIEW public_cube_seasons AS
        WITH {_BINNED_CTE},
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
    """)

    op.execute(f"""
        CREATE OR REPLACE VIEW public_cube_season_breakdown AS
        WITH {_BINNED_CTE}
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
            {_AVATAR_URL_SQL} AS avatar_url
        FROM binned b;
    """)

    for view in ("public_cube_seasons", "public_cube_season_breakdown", "public_cube_season_events"):
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO anon;")
        _grant_if_exists(view, "GRANT SELECT ON public.%s TO authenticated;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_cube_season_events;")
    op.execute("DROP VIEW IF EXISTS public_cube_season_breakdown;")
    op.execute("DROP VIEW IF EXISTS public_cube_seasons;")


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
