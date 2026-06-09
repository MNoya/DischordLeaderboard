"""Add pod_draft_events.kind (tournament/mock), allow null sesh_message_id, expose kind in the
public view, and hide future-dated sets from public_sets so an unreleased set (e.g. MSH) stays off
the leaderboard until its Arena release date.

Revision ID: d5m6o7c8k9d0
Revises: v9w0x1y2z3a4
Create Date: 2026-06-09 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d5m6o7c8k9d0"
down_revision: Union[str, None] = "v9w0x1y2z3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""

_SLUG_SQL = "trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g'))"


def _events_view(*, with_kind: bool) -> str:
    kind_col = "pde.kind," if with_kind else ""
    # Mock events carry no placements, so finalize is event-level (finalized_at) OR everyone placed.
    finalized = (
        "(pde.finalized_at IS NOT NULL OR counts.all_placed) AS is_finalized"
        if with_kind
        else "counts.is_finalized"
    )
    counts = (
        "COALESCE(BOOL_AND(pdp.placement IS NOT NULL), FALSE) AS all_placed"
        if with_kind
        else "COALESCE(BOOL_AND(pdp.placement IS NOT NULL), FALSE) AS is_finalized"
    )
    return f"""
        CREATE VIEW public_pod_draft_events AS
        SELECT
            pde.id            AS event_id,
            {_SLUG_SQL}       AS slug,
            pde.name,
            pde.set_code,
            {kind_col}
            pde.event_date,
            pde.event_time,
            pde.format_label,
            pde.discord_event_id,
            COALESCE(rounds.total_rounds, 0)::int AS total_rounds,
            champ.player_slug         AS champion_player_slug,
            champ.display_name        AS champion_display_name,
            champ.avatar_url          AS champion_avatar_url,
            champ.deck_colors         AS champion_deck_colors,
            champ.record              AS champion_record,
            counts.participant_count,
            {finalized}
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
                {counts}
            FROM pod_draft_participants pdp
            WHERE pdp.event_id = pde.id
        ) counts ON TRUE
        ORDER BY pde.event_time DESC NULLS LAST;
    """


def upgrade() -> None:
    op.add_column(
        "pod_draft_events",
        sa.Column("kind", sa.String(), nullable=False, server_default="tournament"),
    )
    op.alter_column("pod_draft_events", "sesh_message_id", nullable=True)

    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
    op.execute(_events_view(with_kind=True))
    op.execute("GRANT SELECT ON public_pod_draft_events TO anon;")

    op.execute("""
        CREATE OR REPLACE VIEW public_sets AS
        SELECT
            code,
            name,
            start_date,
            end_date,
            (end_date IS NOT NULL AND CURRENT_DATE BETWEEN start_date AND end_date) AS is_active
        FROM sets
        WHERE start_date <= CURRENT_DATE;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_sets AS
        SELECT
            code,
            name,
            start_date,
            end_date,
            (end_date IS NOT NULL AND CURRENT_DATE BETWEEN start_date AND end_date) AS is_active
        FROM sets;
    """)

    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
    op.execute(_events_view(with_kind=False))
    op.execute("GRANT SELECT ON public_pod_draft_events TO anon;")

    op.alter_column("pod_draft_events", "sesh_message_id", nullable=False)
    op.drop_column("pod_draft_events", "kind")
