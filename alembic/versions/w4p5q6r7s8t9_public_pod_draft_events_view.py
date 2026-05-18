"""Add public_pod_draft_events + public_pod_draft_event_participants views

Per-event summary (champion, participant count, finalized flag) for the pod
draft hub page, plus a participants view powering the expandable per-event
summary row (standings + deck colors + draft log URLs).

Revision ID: w4p5q6r7s8t9
Revises: v3o4p5q6r7s8
Create Date: 2026-05-17 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "w4p5q6r7s8t9"
down_revision: Union[str, None] = "v3o4p5q6r7s8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""

_SLUG_SQL = "trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g'))"


def upgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE VIEW public_pod_draft_events AS
        SELECT
            pde.id            AS event_id,
            {_SLUG_SQL}       AS slug,
            pde.name,
            pde.set_code,
            pde.event_date,
            pde.event_time,
            pde.format_label,
            COALESCE(rounds.total_rounds, 0)::int AS total_rounds,
            champ.player_slug         AS champion_player_slug,
            champ.display_name        AS champion_display_name,
            champ.avatar_url          AS champion_avatar_url,
            champ.deck_colors         AS champion_deck_colors,
            champ.record              AS champion_record,
            counts.participant_count,
            counts.is_finalized
        FROM pod_draft_events pde
        LEFT JOIN LATERAL (
            SELECT MAX(round)::int AS total_rounds
            FROM pod_draft_matches
            WHERE event_id = pde.id
        ) rounds ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                pdp.display_name,
                pdp.record,
                pdp.deck_colors,
                p.slug AS player_slug,
                {_AVATAR_URL_SQL} AS avatar_url
            FROM pod_draft_participants pdp
            LEFT JOIN players p ON p.id = pdp.player_id
            WHERE pdp.event_id = pde.id AND pdp.placement = 1
            ORDER BY pdp.display_name ASC
            LIMIT 1
        ) champ ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*)::int AS participant_count,
                COALESCE(BOOL_AND(pdp.placement IS NOT NULL), FALSE) AS is_finalized
            FROM pod_draft_participants pdp
            WHERE pdp.event_id = pde.id
        ) counts ON TRUE
        ORDER BY pde.event_time DESC NULLS LAST;
    """)
    op.execute("GRANT SELECT ON public_pod_draft_events TO anon;")

    op.execute(f"""
        CREATE OR REPLACE VIEW public_pod_draft_event_participants AS
        SELECT
            pdp.event_id,
            pdp.display_name,
            pdp.placement,
            pdp.record,
            pdp.deck_colors,
            pdp.draft_log_url,
            pdp.deck_screenshot_url,
            p.slug                          AS player_slug,
            p.display_name                  AS player_display_name,
            {_AVATAR_URL_SQL}               AS avatar_url
        FROM pod_draft_participants pdp
        LEFT JOIN players p ON p.id = pdp.player_id;
    """)
    op.execute("GRANT SELECT ON public_pod_draft_event_participants TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_event_participants;")
    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
