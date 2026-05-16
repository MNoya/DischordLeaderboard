"""Add public_player_pod_stats view

Per-(set_code, slug) aggregation of finalized pod participations so the
frontend can show a pod-filtered leaderboard. Kept separate from
public_player_format_breakdown to keep pod stats out of the per-format
scoring donut (pods have no scoring formula today).

Revision ID: o5e6f7g8h9i0
Revises: n4d5e6f7g8h9
Create Date: 2026-05-16 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "o5e6f7g8h9i0"
down_revision: Union[str, None] = "n4d5e6f7g8h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def upgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE VIEW public_player_pod_stats AS
        SELECT
            pde.set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            COUNT(*)::int AS events,
            COALESCE(SUM(COALESCE(NULLIF(split_part(pdp.record, '-', 1), ''), '0')::int), 0)::int AS wins,
            COALESCE(SUM(COALESCE(NULLIF(split_part(pdp.record, '-', 2), ''), '0')::int), 0)::int AS losses,
            COALESCE(SUM(CASE WHEN pdp.placement = 1 THEN 1 ELSE 0 END), 0)::int AS trophies,
            MAX(pde.event_time) AS last_finished_at
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true AND pdp.placement IS NOT NULL
        GROUP BY pde.set_code, p.slug, p.display_name, p.avatar_hash, p.discord_id;
    """)
    op.execute("GRANT SELECT ON public_player_pod_stats TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_pod_stats;")
