"""Compute live W-L in public_pod_draft_event_participants

While a pod is in progress, pod_draft_participants.record is NULL — it only gets
populated when finalize_champion runs. The shield UI then renders 0-0 for every
seat. Re-define the view to COALESCE the persisted record with one derived from
pod_draft_matches.winner_name so the frontend sees per-round W-L on refresh.

Revision ID: g4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-05-21 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "g4b5c6d7e8f9"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


_LIVE_RECORD_SQL = """\
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


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_event_participants;")
    op.execute(f"""
        CREATE VIEW public_pod_draft_event_participants AS
        SELECT
            pdp.event_id,
            pdp.display_name,
            pdp.seat_index,
            pdp.placement,
            {_LIVE_RECORD_SQL}              AS record,
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


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_event_participants;")
    op.execute(f"""
        CREATE VIEW public_pod_draft_event_participants AS
        SELECT
            pdp.event_id,
            pdp.display_name,
            pdp.seat_index,
            pdp.placement,
            pdp.record,
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
