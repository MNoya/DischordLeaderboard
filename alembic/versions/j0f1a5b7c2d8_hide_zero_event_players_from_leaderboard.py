"""Hide zero-event players from public_leaderboard

Refresh writes a PlayerSetScore(score=0, trophies=0) row for every active
player even if they haven't drafted in the set yet, which surfaces them at
the bottom of the leaderboard with rank N and a "0 0 0" record. Filter
those out so a player only appears once they have at least one event.

Revision ID: j0f1a5b7c2d8
Revises: i9e1f5b3a7d4
Create Date: 2026-05-12 03:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "j0f1a5b7c2d8"
down_revision: Union[str, None] = "i9e1f5b3a7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def upgrade() -> None:
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
        ),
        ranked AS (
            SELECT *
            FROM player_totals
            WHERE events > 0
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
        FROM ranked pt
        JOIN players p ON p.id = pt.player_id
        JOIN sets s ON s.id = pt.set_id
        WHERE p.active = true;
    """)


def downgrade() -> None:
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
