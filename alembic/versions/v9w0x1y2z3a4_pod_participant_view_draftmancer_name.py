"""Expose pod_draft_participants.draftmancer_name in the public participants view

Match rows carry Draftmancer userNames; the pod page joined them to seats by display_name,
which only works while display_name happens to equal the Draftmancer name. Exposing the real
key lets the frontend join on it and frees display_name to be presentation-only.

Revision ID: v9w0x1y2z3a4
Revises: t8u9v0w1x2y3
Create Date: 2026-06-07 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "v9w0x1y2z3a4"
down_revision: Union[str, None] = "t8u9v0w1x2y3"
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


def _recreate_view(with_draftmancer_name: bool) -> None:
    draftmancer_name_sql = "pdp.draftmancer_name," if with_draftmancer_name else ""
    op.execute("DROP VIEW IF EXISTS public_pod_draft_event_participants;")
    op.execute(f"""
        CREATE VIEW public_pod_draft_event_participants AS
        SELECT
            pdp.event_id,
            pdp.display_name,
            {draftmancer_name_sql}
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


def upgrade() -> None:
    _recreate_view(with_draftmancer_name=True)


def downgrade() -> None:
    _recreate_view(with_draftmancer_name=False)
