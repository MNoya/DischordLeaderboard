"""Add pod_draft_events.closed_decklist and expose it in public_pod_draft_events

Closed Decklist mode hides a pod's decklists and draft log on the website until the pod finishes.
The flag is per-pod; the site gates visibility on it. Championship pods default to closed.

Revision ID: f0c1d2e3a4b5
Revises: c4e6a8b0d2f3
Create Date: 2026-07-23 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f0c1d2e3a4b5"
down_revision: Union[str, None] = "c4e6a8b0d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL = (
    "CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL "
    "THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128' "
    "ELSE NULL END"
)

_CHAMP_LATERAL = f"""
    LEFT JOIN LATERAL (
        SELECT
            COALESCE(p.display_name, pdp.display_name) AS display_name,
            pdp.record,
            pdp.deck_colors,
            p.slug AS player_slug,
            {_AVATAR_URL} AS avatar_url
        FROM pod_draft_participants pdp
        LEFT JOIN players p ON p.id = pdp.player_id
        WHERE pdp.event_id = ev.id AND pdp.placement = 1
        ORDER BY pdp.display_name ASC
        LIMIT 1
    ) champ ON TRUE
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*)::int AS participant_count,
            COALESCE(BOOL_AND(pdp.placement IS NOT NULL), FALSE) AS all_placed
        FROM pod_draft_participants pdp
        WHERE pdp.event_id = ev.id
    ) counts ON TRUE
    LEFT JOIN LATERAL (
        SELECT MAX(round)::int AS total_rounds
        FROM pod_draft_matches
        WHERE event_id = ev.id
    ) rounds ON TRUE
"""


def _events_view(*, with_closed_decklist: bool) -> str:
    closed_col = "    ev.closed_decklist          AS closed_decklist,\n" if with_closed_decklist else ""
    body = r"""
CREATE VIEW public_pod_draft_events AS
WITH ev AS (
    SELECT
        pde.*,
        trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g')) AS raw_slug,
        COALESCE(NULLIF((regexp_match(pde.name, 'Table\s+(\d+)\s*$', 'i'))[1], '')::int, 1) AS tbl_index,
        (pde.event_time <= now() OR pde.finalized_at IS NOT NULL) AS executed
    FROM pod_draft_events pde
),
ranked AS (
    SELECT id,
        ROW_NUMBER() OVER (PARTITION BY set_code ORDER BY event_time, tbl_index, id) AS ordinal
    FROM ev
    WHERE executed AND kind IS DISTINCT FROM 'mock'
)
SELECT
    ev.id AS event_id,
    CASE
        WHEN COUNT(*) OVER (PARTITION BY ev.raw_slug) > 1
        THEN ev.raw_slug || '-' || left(ev.id, 8)
        ELSE ev.raw_slug
    END AS slug,
    ev.name,
    ev.set_code,
    ev.kind,
    ev.event_date,
    ev.event_time,
    ev.format_label,
    COALESCE(rounds.total_rounds, 0)::int AS total_rounds,
    champ.player_slug         AS champion_player_slug,
    champ.display_name        AS champion_display_name,
    champ.avatar_url          AS champion_avatar_url,
    champ.deck_colors         AS champion_deck_colors,
    champ.record              AS champion_record,
    counts.participant_count,
    (ev.finalized_at IS NOT NULL OR counts.all_placed) AS is_finalized,
__CLOSED__    ranked.ordinal,
    ev.tbl_index              AS table_index,
    (ev.pairing_mode = 'team') AS is_team_draft
FROM ev
LEFT JOIN ranked ON ranked.id = ev.id
__CHAMP__
ORDER BY ev.event_time DESC NULLS LAST;
"""
    return body.replace("__CLOSED__", closed_col).replace("__CHAMP__", _CHAMP_LATERAL)


def _recreate_view(*, with_closed_decklist: bool) -> None:
    op.execute(_events_view(with_closed_decklist=with_closed_decklist))
    op.execute("GRANT SELECT ON public_pod_draft_events TO anon;")
    op.execute("GRANT SELECT ON public_pod_draft_events TO authenticated;")


def upgrade() -> None:
    op.add_column(
        "pod_draft_events",
        sa.Column("closed_decklist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute("UPDATE pod_draft_events SET closed_decklist = TRUE WHERE lower(name) LIKE '%championship%';")
    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
    _recreate_view(with_closed_decklist=True)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
    op.drop_column("pod_draft_events", "closed_decklist")
    _recreate_view(with_closed_decklist=False)
