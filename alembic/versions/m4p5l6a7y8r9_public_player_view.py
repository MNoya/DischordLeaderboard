"""Add public_player view so opted-out profiles stay reachable by direct link

public_leaderboard gates on leaderboard_opt_in, so the profile page headline
404'd for anyone who hid their rank. public_player mirrors that view without
the opt-in filter, giving the profile page an ungated headline source. Rank is
still derived from the gated leaderboard, so an opted-out player resolves to
unranked rather than vanishing.

Revision ID: m4p5l6a7y8r9
Revises: l3o4p5t6q7r8
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op


revision: str = "m4p5l6a7y8r9"
down_revision: Union[str, None] = "l3o4p5t6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def upgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE VIEW public_player AS
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
    op.execute("GRANT SELECT ON public_player TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player;")
