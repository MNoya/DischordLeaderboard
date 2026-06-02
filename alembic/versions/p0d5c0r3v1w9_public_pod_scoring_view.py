"""Add public_pod_scoring view for leaderboard pod points

Per (slug, set_code): pod trophy + 2-1 counts, event count, W-L, and display
name/avatar — so the browser-direct frontend can add pod points, render a Pod
row in the breakdown / Pod-filtered board, and surface pod-only entrants (who
have no player_stats and so aren't in public_player). Pods are always public:
filtered on active only, never leaderboard_opt_in. A trophy is a 3-0 record OR a
pod win (placement 1); a 2-1 that won the pod is the trophy, not a 2-1.

Revision ID: p0d5c0r3v1w9
Revises: m4p5l6a7y8r9
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "p0d5c0r3v1w9"
down_revision: Union[str, None] = "m4p5l6a7y8r9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""

_WINS_SQL = "COALESCE(NULLIF(split_part(pdp.record, '-', 1), ''), '0')::int"
_LOSSES_SQL = "COALESCE(NULLIF(split_part(pdp.record, '-', 2), ''), '0')::int"


def upgrade() -> None:
    op.execute(f"""
        CREATE VIEW public_pod_scoring AS
        SELECT
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            pde.set_code,
            COUNT(*) FILTER (WHERE pdp.record = '3-0' OR pdp.placement = 1)::int AS trophies,
            COUNT(*) FILTER (WHERE pdp.record = '2-1' AND pdp.placement <> 1)::int AS wins_2_1,
            COUNT(*)::int AS events,
            COALESCE(SUM({_WINS_SQL}), 0)::int AS wins,
            COALESCE(SUM({_LOSSES_SQL}), 0)::int AS losses
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND pdp.placement IS NOT NULL
        GROUP BY p.slug, p.display_name, p.avatar_hash, p.discord_id, pde.set_code;
    """)
    op.execute("GRANT SELECT ON public_pod_scoring TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_scoring;")
