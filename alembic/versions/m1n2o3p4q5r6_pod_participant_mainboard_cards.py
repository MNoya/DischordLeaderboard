"""Add resolved mainboard_cards and expose it on public_pod_draft_event_participants

The pod page renders a player's maindeck from the draft log when no deck screenshot is posted.
mainboard_card_ids already stores the raw Draftmancer ids; mainboard_cards stores the resolved,
renderable form (nonbasic spells grouped by name with counts, plus the basic-land tally) so the
browser never needs the gzipped draft log. Backfilled by re-ingesting past events.

Revision ID: m1n2o3p4q5r6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
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


def _recreate_view(with_mainboard: bool) -> None:
    mainboard_col = "pdp.mainboard_cards," if with_mainboard else ""
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
            {mainboard_col}
            p.slug                          AS player_slug,
            p.display_name                  AS player_display_name,
            {_AVATAR_URL_SQL}               AS avatar_url
        FROM pod_draft_participants pdp
        LEFT JOIN players p ON p.id = pdp.player_id;
    """)
    op.execute("GRANT SELECT ON public_pod_draft_event_participants TO anon;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
                GRANT SELECT ON public_pod_draft_event_participants TO authenticated;
            END IF;
        END
        $$;
    """)


def upgrade() -> None:
    op.add_column("pod_draft_participants", sa.Column("mainboard_cards", JSONB(), nullable=True))
    _recreate_view(with_mainboard=True)


def downgrade() -> None:
    _recreate_view(with_mainboard=False)
    op.drop_column("pod_draft_participants", "mainboard_cards")
