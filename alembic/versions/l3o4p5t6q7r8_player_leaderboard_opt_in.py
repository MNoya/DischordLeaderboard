"""Add players.leaderboard_opt_in and gate the ranked view on it

Pod-only players (no 17lands token) were being fetched by the periodic refresh,
404ing on a NULL token, getting flagged token_invalid, and DM'd to /relink. The
refresh query now requires a token; this migration un-flags everyone wrongly
invalidated and adds an explicit ranking opt-in so a pod player can share a
17lands link for replays without landing on the public leaderboard.

public_leaderboard now requires leaderboard_opt_in. The trophy feed, profile
breakdown, and pod views are untouched, so an opted-out player keeps full
presence everywhere except the numbered index.

Revision ID: l3o4p5t6q7r8
Revises: 99fd7038c078
Create Date: 2026-05-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "l3o4p5t6q7r8"
down_revision: Union[str, None] = "99fd7038c078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("leaderboard_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute("UPDATE players SET leaderboard_opt_in = (seventeenlands_token IS NOT NULL)")
    op.execute("UPDATE players SET token_invalid = false WHERE token_invalid = true AND seventeenlands_token IS NULL")
    op.alter_column("players", "leaderboard_opt_in", server_default=None)

    op.execute(f"""
        CREATE OR REPLACE VIEW public_leaderboard AS
        SELECT
            s.code AS set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            COALESCE(SUM(ps.events), 0)::int AS events,
            COALESCE(SUM(ps.wins), 0)::int AS wins,
            COALESCE(SUM(ps.losses), 0)::int AS losses,
            COALESCE(SUM(ps.trophies), 0)::int AS trophies,
            MAX(ps.last_fetched_at) AS last_calculated_at
        FROM players p
        JOIN player_stats ps ON ps.player_id = p.id
        JOIN sets s ON s.id = ps.set_id
        WHERE p.active = true AND p.leaderboard_opt_in = true
        GROUP BY s.code, p.slug, p.display_name, p.avatar_hash, p.discord_id
        HAVING SUM(ps.events) > 0;
    """)
    op.execute("GRANT SELECT ON public_leaderboard TO anon;")


def downgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE VIEW public_leaderboard AS
        SELECT
            s.code AS set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            COALESCE(SUM(ps.events), 0)::int AS events,
            COALESCE(SUM(ps.wins), 0)::int AS wins,
            COALESCE(SUM(ps.losses), 0)::int AS losses,
            COALESCE(SUM(ps.trophies), 0)::int AS trophies,
            MAX(ps.last_fetched_at) AS last_calculated_at
        FROM players p
        JOIN player_stats ps ON ps.player_id = p.id
        JOIN sets s ON s.id = ps.set_id
        WHERE p.active = true
        GROUP BY s.code, p.slug, p.display_name, p.avatar_hash, p.discord_id
        HAVING SUM(ps.events) > 0;
    """)
    op.execute("GRANT SELECT ON public_leaderboard TO anon;")
    op.drop_column("players", "leaderboard_opt_in")
