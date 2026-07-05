"""Surface end_rank in public_recent_trophies

Lets the leaderboard sidebar filter trophies by the Arena rank held when the
trophy run finished.

Revision ID: b3t7r9o1p5h2
Revises: a9r2k4e6n8d0
Create Date: 2026-07-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b3t7r9o1p5h2"
down_revision: Union[str, None] = "a9r2k4e6n8d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """
    CASE
        WHEN p.avatar_hash IS NULL OR p.discord_id IS NULL THEN NULL
        ELSE 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    END
"""


def _view_sql(end_rank: str) -> str:
    return f"""
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
            de.finished_at,
            de.seventeenlands_event_id{end_rank}
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE de.is_trophy = true AND p.active = true
        ORDER BY de.finished_at DESC NULLS LAST;
    """


def upgrade() -> None:
    op.execute(_view_sql(",\n            de.end_rank"))
    op.execute("GRANT SELECT ON public_recent_trophies TO anon;")
    op.execute("GRANT SELECT ON public_recent_trophies TO authenticated;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_recent_trophies;")
    op.execute(_view_sql(""))
    op.execute("GRANT SELECT ON public_recent_trophies TO anon;")
    op.execute("GRANT SELECT ON public_recent_trophies TO authenticated;")
