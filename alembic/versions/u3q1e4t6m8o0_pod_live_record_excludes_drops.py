"""Exclude (skipped) matches from live record in public_pod_draft_event_participants

The live W-L fallback in public_pod_draft_event_participants counts any non-null
winner_name that isn't the participant as a loss, which incorrectly counts
"(skipped)" sentinel rows ("No Match Played") as losses. Drops aren't losses —
restrict the loss filter to non-skipped winners. Finalized records (loaded via
_load_matches) already exclude skipped, so this only affects in-progress pods.

Revision ID: u3q1e4t6m8o0
Revises: t2p0d3s5l7n9
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op


revision: str = "u3q1e4t6m8o0"
down_revision: Union[str, None] = "t2p0d3s5l7n9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


_LIVE_RECORD_SQL_NEW = """\
COALESCE(
    pdp.record,
    (
        SELECT (COUNT(*) FILTER (
                WHERE pdm.winner_name = pdp.draftmancer_name
            ))::text
            || '-'
            || (COUNT(*) FILTER (
                WHERE pdm.winner_name IS NOT NULL
                  AND pdm.winner_name <> pdp.draftmancer_name
                  AND pdm.winner_name <> '(skipped)'
            ))::text
        FROM pod_draft_matches pdm
        WHERE pdm.event_id = pdp.event_id
          AND pdp.draftmancer_name IS NOT NULL
          AND (pdm.player_a_name = pdp.draftmancer_name OR pdm.player_b_name = pdp.draftmancer_name)
    )
)"""


_LIVE_RECORD_SQL_OLD = """\
COALESCE(
    pdp.record,
    (
        SELECT (COUNT(*) FILTER (WHERE pdm.winner_name = pdp.draftmancer_name))::text
            || '-'
            || (COUNT(*) FILTER (
                WHERE pdm.winner_name IS NOT NULL
                  AND pdm.winner_name <> pdp.draftmancer_name
            ))::text
        FROM pod_draft_matches pdm
        WHERE pdm.event_id = pdp.event_id
          AND pdp.draftmancer_name IS NOT NULL
          AND (pdm.player_a_name = pdp.draftmancer_name OR pdm.player_b_name = pdp.draftmancer_name)
    )
)"""


def _recreate_view(live_record_sql: str) -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_event_participants;")
    op.execute(f"""
        CREATE VIEW public_pod_draft_event_participants AS
        SELECT
            pdp.event_id,
            pdp.display_name,
            pdp.seat_index,
            pdp.placement,
            {live_record_sql}              AS record,
            pdp.deck_colors,
            pdp.draft_log_url,
            pdp.deck_screenshot_url,
            pdp.deck_screenshot_caption,
            p.slug                          AS player_slug,
            p.display_name                  AS player_display_name,
            {_AVATAR_URL_SQL}               AS avatar_url
        FROM pod_draft_participants pdp
        LEFT JOIN players p ON p.id = pdp.player_id;
    """)
    op.execute("GRANT SELECT ON public_pod_draft_event_participants TO anon;")


def upgrade() -> None:
    _recreate_view(_LIVE_RECORD_SQL_NEW)


def downgrade() -> None:
    _recreate_view(_LIVE_RECORD_SQL_OLD)
