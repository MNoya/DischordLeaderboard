"""create public_* views

Revision ID: d4f6a8c0e2f4
Revises: c3e5f7b9d1f3
Create Date: 2026-05-09

Creates the six curated views the frontend consumes (frontend-spec.md → Data
contract) and grants SELECT to anon. Base tables stay locked with RLS; views
are the only public surface.

Views:
  public_sets                    — set list with computed is_active
  public_leaderboard             — per-(player, set) score with rank, derived avatar_url
  public_player_format_breakdown — per-format score_contribution (mirrors compute_score)
  public_player_draft_events     — per-event row for archetype + draft history
  public_archetype_leaderboard   — per-(player, set, archetype) leaderboard
  public_recent_trophies         — recent is_trophy=true draft_events feed
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d4f6a8c0e2f4"
down_revision: Union[str, None] = "c3e5f7b9d1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Discord CDN URL fragment, used in three views. 128px is the smallest size
# that doesn't pixelate on retina avatar circles
_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


# Format-group mapping — mirror of bot/scoring.py DEFAULT_QUEUE_GROUPS
_FORMAT_LABEL_CASE = """\
CASE
    WHEN ps.format = 'PremierDraft' THEN 'Premier'
    WHEN ps.format = 'TradDraft' THEN 'Trad'
    WHEN ps.format IN ('Sealed', 'TradSealed', 'ArenaDirect_Sealed', 'QualifierPlayInSealed') THEN 'Sealed'
    WHEN ps.format IN ('QuickDraft', 'PickTwoDraft', 'Emblem_QuickDraft') THEN 'Quick'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft1' THEN 'LCQ Draft 1'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft2' THEN 'LCQ Draft 2'
    ELSE NULL
END"""


def upgrade() -> None:
    # ── public_sets ──────────────────────────────────────────────────────
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

    # ── public_leaderboard ───────────────────────────────────────────────
    op.execute(f"""
        CREATE OR REPLACE VIEW public_leaderboard AS
        WITH player_totals AS (
            SELECT
                pss.player_id,
                pss.set_id,
                pss.score,
                pss.trophies,
                pss.last_calculated_at,
                COALESCE(SUM(ps.events), 0)::int AS events,
                COALESCE(SUM(ps.wins), 0)::int AS wins,
                COALESCE(SUM(ps.losses), 0)::int AS losses
            FROM player_set_scores pss
            LEFT JOIN player_stats ps
                ON ps.player_id = pss.player_id AND ps.set_id = pss.set_id
            GROUP BY pss.player_id, pss.set_id, pss.score, pss.trophies, pss.last_calculated_at
        )
        SELECT
            s.code AS set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            RANK() OVER (PARTITION BY s.code ORDER BY pt.score DESC)::int AS rank,
            pt.score::numeric AS score,
            pt.trophies,
            pt.events,
            pt.wins,
            pt.losses,
            pt.last_calculated_at
        FROM player_totals pt
        JOIN players p ON p.id = pt.player_id
        JOIN sets s ON s.id = pt.set_id
        WHERE p.active = true;
    """)

    # ── public_player_format_breakdown ───────────────────────────────────
    # Mirrors bot/scoring.compute_score per group:
    #   standard: trophies * points * (trophies/events) * (trophies/(trophies+2))
    #   LCQ Draft 2: wins * (wins/(wins+losses)) * 10
    op.execute(f"""
        CREATE OR REPLACE VIEW public_player_format_breakdown AS
        WITH grouped AS (
            SELECT
                s.code AS set_code,
                p.slug,
                {_FORMAT_LABEL_CASE} AS format_label,
                SUM(ps.events)::int AS events,
                SUM(ps.wins)::int AS wins,
                SUM(ps.losses)::int AS losses,
                SUM(ps.trophies)::int AS trophies
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN sets s ON s.id = ps.set_id
            WHERE p.active = true
            GROUP BY s.code, p.slug, {_FORMAT_LABEL_CASE}
        )
        SELECT
            set_code,
            slug,
            format_label,
            events,
            wins,
            losses,
            trophies,
            ROUND(
                CASE
                    WHEN format_label = 'LCQ Draft 2' AND (wins + losses) > 0 AND wins > 0
                        THEN wins::numeric * (wins::numeric / (wins + losses)) * 10
                    WHEN format_label IN ('Premier','Trad','Sealed','Quick','LCQ Draft 1')
                         AND trophies > 0 AND events > 0
                        THEN trophies::numeric
                             * (CASE format_label
                                    WHEN 'Premier' THEN 10
                                    WHEN 'Trad' THEN 9
                                    WHEN 'Sealed' THEN 8
                                    WHEN 'Quick' THEN 3
                                    WHEN 'LCQ Draft 1' THEN 30
                                END)
                             * (trophies::numeric / events)
                             * (trophies::numeric / (trophies + 2))
                    ELSE 0
                END,
                2
            ) AS score_contribution
        FROM grouped
        WHERE format_label IS NOT NULL;
    """)

    # ── public_player_draft_events ───────────────────────────────────────
    op.execute("""
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
            de.finished_at
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE p.active = true;
    """)

    # ── public_archetype_leaderboard ─────────────────────────────────────
    op.execute(f"""
        CREATE OR REPLACE VIEW public_archetype_leaderboard AS
        SELECT
            s.code AS set_code,
            pas.archetype,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            RANK() OVER (
                PARTITION BY s.code, pas.archetype
                ORDER BY pas.score DESC,
                         (pas.wins::numeric / NULLIF(pas.wins + pas.losses, 0)) DESC
            )::int AS rank,
            pas.score::numeric AS score,
            pas.trophies,
            pas.events,
            pas.wins,
            pas.losses,
            pas.last_calculated_at
        FROM player_archetype_scores pas
        JOIN players p ON p.id = pas.player_id
        JOIN sets s ON s.id = pas.set_id
        WHERE p.active = true;
    """)

    # ── public_recent_trophies ───────────────────────────────────────────
    # ORDER BY in a view doesn't bind consumers, but it lets us LIMIT cheaply
    # against a sorted index-friendly stream
    op.execute(f"""
        CREATE OR REPLACE VIEW public_recent_trophies AS
        SELECT
            s.code AS set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            de.format,
            de.colors,
            de.wins,
            de.losses,
            de.finished_at
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE de.is_trophy = true AND p.active = true
        ORDER BY de.finished_at DESC NULLS LAST;
    """)

    # ── grants ───────────────────────────────────────────────────────────
    # Anon role gets SELECT on the curated views; base tables stay locked
    # under RLS with no anon grants. The role is built-in on Supabase but not
    # on vanilla Postgres (CI), so create it idempotently first.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
                CREATE ROLE anon NOLOGIN;
            END IF;
        END
        $$;
    """)
    op.execute("GRANT SELECT ON public_sets                    TO anon;")
    op.execute("GRANT SELECT ON public_leaderboard             TO anon;")
    op.execute("GRANT SELECT ON public_player_format_breakdown TO anon;")
    op.execute("GRANT SELECT ON public_player_draft_events     TO anon;")
    op.execute("GRANT SELECT ON public_archetype_leaderboard   TO anon;")
    op.execute("GRANT SELECT ON public_recent_trophies         TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_recent_trophies;")
    op.execute("DROP VIEW IF EXISTS public_archetype_leaderboard;")
    op.execute("DROP VIEW IF EXISTS public_player_draft_events;")
    op.execute("DROP VIEW IF EXISTS public_player_format_breakdown;")
    op.execute("DROP VIEW IF EXISTS public_leaderboard;")
    op.execute("DROP VIEW IF EXISTS public_sets;")
