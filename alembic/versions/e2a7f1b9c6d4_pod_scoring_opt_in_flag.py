"""Expose leaderboard_opt_in on public_pod_scoring

The overall leaderboard admits pod-only entrants from this view, so it needs to
know who opted out: opted-out players stay in the pod standings but drop off the
overall board. The dedicated pod views read the same rows and ignore the flag.

Revision ID: e2a7f1b9c6d4
Revises: 2d56f503f8c7
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e2a7f1b9c6d4"
down_revision: Union[str, None] = "2d56f503f8c7"
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
        CREATE OR REPLACE VIEW public_pod_scoring AS
        SELECT
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            pde.set_code,
            COUNT(*) FILTER (WHERE pdp.record = '3-0' OR pdp.placement = 1)::int AS trophies,
            COUNT(*) FILTER (WHERE pdp.record = '2-1' AND pdp.placement <> 1)::int AS wins_2_1,
            COUNT(*)::int AS events,
            COALESCE(SUM({_WINS_SQL}), 0)::int AS wins,
            COALESCE(SUM({_LOSSES_SQL}), 0)::int AS losses,
            p.leaderboard_opt_in
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND pdp.placement IS NOT NULL
        GROUP BY p.slug, p.display_name, p.avatar_hash, p.discord_id, pde.set_code, p.leaderboard_opt_in;
    """)
    op.execute("GRANT SELECT ON public_pod_scoring TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_scoring;")
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
