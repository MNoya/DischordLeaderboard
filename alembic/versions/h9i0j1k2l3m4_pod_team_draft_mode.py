"""Add team-draft support: team columns and record-keyed pod scoring

Team-draft pods split the roster into two teams by draft-seat parity. `pod_draft_participants.team`
records the side ('A'/'B'); `pod_draft_events.team_a_thread_id` / `team_b_thread_id` hold the private
per-team Discord threads. All nullable — non-team pods leave them empty.

Team participants finalize with a record but no placement, since a team pod has no individual champion.
public_pod_scoring and public_player_pod_stats keyed their row filters (and trophy/2-1 counts) on
placement, which would drop team finishes entirely; key the row filters on record, count trophies as a
3-0 record or a pod win, and make the 2-1 count null-safe. The placement=1 trophy rule stays for
regular pods.

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-07-11 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "h9i0j1k2l3m4"
down_revision: Union[str, None] = "g8h9i0j1k2l3"
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
    op.add_column("pod_draft_participants", sa.Column("team", sa.String(), nullable=True))
    op.add_column("pod_draft_events", sa.Column("team_a_thread_id", sa.String(), nullable=True))
    op.add_column("pod_draft_events", sa.Column("team_b_thread_id", sa.String(), nullable=True))
    op.execute(f"""
        CREATE OR REPLACE VIEW public_pod_scoring AS
        SELECT
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            pde.set_code,
            COUNT(*) FILTER (WHERE pdp.record = '3-0' OR pdp.placement = 1)::int AS trophies,
            COUNT(*) FILTER (WHERE pdp.record = '2-1' AND pdp.placement IS DISTINCT FROM 1)::int AS wins_2_1,
            COUNT(*)::int AS events,
            COALESCE(SUM({_WINS_SQL}), 0)::int AS wins,
            COALESCE(SUM({_LOSSES_SQL}), 0)::int AS losses,
            p.leaderboard_opt_in
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND pdp.record IS NOT NULL
        GROUP BY p.slug, p.display_name, p.avatar_hash, p.discord_id, pde.set_code, p.leaderboard_opt_in;
    """)
    op.execute(f"""
        CREATE OR REPLACE VIEW public_player_pod_stats AS
        SELECT
            pde.set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            COUNT(*)::int AS events,
            COALESCE(SUM({_WINS_SQL}), 0)::int AS wins,
            COALESCE(SUM({_LOSSES_SQL}), 0)::int AS losses,
            COUNT(*) FILTER (WHERE pdp.record = '3-0' OR pdp.placement = 1)::int AS trophies,
            MAX(pde.event_time) AS last_finished_at
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true AND pdp.record IS NOT NULL
        GROUP BY pde.set_code, p.slug, p.display_name, p.avatar_hash, p.discord_id;
    """)
    op.execute("GRANT SELECT ON public_pod_scoring TO anon, authenticated;")
    op.execute("GRANT SELECT ON public_player_pod_stats TO anon, authenticated;")


def downgrade() -> None:
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
    op.execute(f"""
        CREATE OR REPLACE VIEW public_player_pod_stats AS
        SELECT
            pde.set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            COUNT(*)::int AS events,
            COALESCE(SUM({_WINS_SQL}), 0)::int AS wins,
            COALESCE(SUM({_LOSSES_SQL}), 0)::int AS losses,
            COALESCE(SUM(CASE WHEN pdp.placement = 1 THEN 1 ELSE 0 END), 0)::int AS trophies,
            MAX(pde.event_time) AS last_finished_at
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true AND pdp.placement IS NOT NULL
        GROUP BY pde.set_code, p.slug, p.display_name, p.avatar_hash, p.discord_id;
    """)
    op.execute("GRANT SELECT ON public_pod_scoring TO anon, authenticated;")
    op.execute("GRANT SELECT ON public_player_pod_stats TO anon, authenticated;")
    op.drop_column("pod_draft_events", "team_b_thread_id")
    op.drop_column("pod_draft_events", "team_a_thread_id")
    op.drop_column("pod_draft_participants", "team")
