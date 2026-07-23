"""Drop pod_draft_events.sesh_message_id

Sesh integration is removed; every pod is bot-native and signal-backed, so the column no longer
tracks anything. public_pod_draft_events selected it, so the view is recreated without it before the
column drop.

Revision ID: f9e8d7c6b5a4
Revises: d5e6f7a8c1b2
Create Date: 2026-07-22 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f9e8d7c6b5a4"
down_revision: Union[str, None] = "d5e6f7a8c1b2"
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

_EVENTS_VIEW = r"""
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
    ranked.ordinal,
    ev.tbl_index              AS table_index,
    (ev.pairing_mode = 'team') AS is_team_draft
FROM ev
LEFT JOIN ranked ON ranked.id = ev.id
__CHAMP__
ORDER BY ev.event_time DESC NULLS LAST;
""".replace("__CHAMP__", _CHAMP_LATERAL)


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
    op.drop_column("pod_draft_events", "sesh_message_id")
    op.execute(_EVENTS_VIEW)
    op.execute("GRANT SELECT ON public_pod_draft_events TO anon;")
    op.execute("GRANT SELECT ON public_pod_draft_events TO authenticated;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
    op.add_column("pod_draft_events", sa.Column("sesh_message_id", sa.String(), nullable=True))
    op.execute(_EVENTS_VIEW.replace(
        "    (ev.pairing_mode = 'team') AS is_team_draft\n",
        "    (ev.pairing_mode = 'team') AS is_team_draft,\n    ev.sesh_message_id\n",
    ))
    op.execute("GRANT SELECT ON public_pod_draft_events TO anon;")
    op.execute("GRANT SELECT ON public_pod_draft_events TO authenticated;")
