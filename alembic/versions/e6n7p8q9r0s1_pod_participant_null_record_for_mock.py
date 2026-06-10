"""Null the live record for mock-draft participants in the public participants view.

The live-record expression COALESCEs the stored record with a win/loss count over the event's
matches. Mock drafts play no matches, so that count resolves to '0-0' and the pod page renders a
fake 0-0 result. Mock events have no rounds, so their record should be null (the frontend then
shows nothing). Adds a join to pod_draft_events for the event kind.

Revision ID: e6n7p8q9r0s1
Revises: d5m6o7c8k9d0
Create Date: 2026-06-09 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e6n7p8q9r0s1"
down_revision: Union[str, None] = "d5m6o7c8k9d0"
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


def _recreate_view(*, mock_aware: bool) -> None:
    record_sql = (
        f"CASE WHEN pde.kind = 'mock' THEN NULL ELSE {_LIVE_RECORD_SQL} END"
        if mock_aware
        else _LIVE_RECORD_SQL
    )
    event_join = "LEFT JOIN pod_draft_events pde ON pde.id = pdp.event_id" if mock_aware else ""
    op.execute("DROP VIEW IF EXISTS public_pod_draft_event_participants;")
    op.execute(f"""
        CREATE VIEW public_pod_draft_event_participants AS
        SELECT
            pdp.event_id,
            pdp.display_name,
            pdp.draftmancer_name,
            pdp.seat_index,
            pdp.placement,
            {record_sql}                    AS record,
            pdp.deck_colors,
            pdp.draft_log_url,
            pdp.deck_screenshot_url,
            pdp.deck_screenshot_caption,
            p.slug                          AS player_slug,
            p.display_name                  AS player_display_name,
            {_AVATAR_URL_SQL}               AS avatar_url
        FROM pod_draft_participants pdp
        LEFT JOIN players p ON p.id = pdp.player_id
        {event_join};
    """)
    op.execute("GRANT SELECT ON public_pod_draft_event_participants TO anon;")


def upgrade() -> None:
    _recreate_view(mock_aware=True)


def downgrade() -> None:
    _recreate_view(mock_aware=False)
