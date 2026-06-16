"""Expose the canonical pod draft artifact via public_pod_draft_log

pod_draft_events.draft_log holds the self-sufficient compact draft (card table with cmc/type, packs,
picks, and built decks as card-array indices) that every pod view derives from client-side. It is
published through public_pod_draft_log, and mainboard_cards is dropped from the participants view.

The redundant mainboard_cards / mainboard_card_ids columns are kept until the historical decks have
been recovered from them into draft_log (bot.scripts.backfill_pod_draft_log); a follow-up migration
drops them.

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, None] = "c3d4e5f6g7h8"
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


def _recreate_participants_view(with_mainboard: bool) -> None:
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
    _grant("public_pod_draft_event_participants")


def _grant(view: str) -> None:
    for role in ("anon", "authenticated"):
        op.execute(f"""
            DO $$
            BEGIN
                IF to_regclass('public.{view}') IS NOT NULL
                   AND EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                    EXECUTE 'GRANT SELECT ON {view} TO {role}';
                END IF;
            END
            $$;
        """)


def upgrade() -> None:
    op.add_column("pod_draft_events", sa.Column("draft_log", JSONB(), nullable=True))

    op.execute("DROP VIEW IF EXISTS public_pod_draft_log;")
    op.execute("""
        CREATE VIEW public_pod_draft_log AS
        SELECT id AS event_id, draft_log
        FROM pod_draft_events
        WHERE draft_log IS NOT NULL;
    """)
    _grant("public_pod_draft_log")

    _recreate_participants_view(with_mainboard=False)


def downgrade() -> None:
    _recreate_participants_view(with_mainboard=True)
    op.execute("DROP VIEW IF EXISTS public_pod_draft_log;")
    op.drop_column("pod_draft_events", "draft_log")
