"""Show the linked player's Discord name for the pod champion in public_pod_draft_events.

The champion lateral selected the participant's Arena display_name, so a linked player's headline
trophy used their Arena handle while the standings rows used their Discord name. Coalesce the linked
player's display_name first, matching podDiscordName on the frontend and list_champions in the bot.

Revision ID: c4d5e6f7a8b9
Revises: a1c2e3f4b5d6
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "a1c2e3f4b5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""

_SLUG_SQL = "trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g'))"


def _events_view(champion_name_sql: str) -> str:
    return f"""
        CREATE VIEW public_pod_draft_events AS
        SELECT
            pde.id            AS event_id,
            {_SLUG_SQL}       AS slug,
            pde.name,
            pde.set_code,
            pde.kind,
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
            (pde.finalized_at IS NOT NULL OR counts.all_placed) AS is_finalized,
            pde.sesh_message_id
        FROM pod_draft_events pde
        LEFT JOIN LATERAL (
            SELECT MAX(round)::int AS total_rounds
            FROM pod_draft_matches
            WHERE event_id = pde.id
        ) rounds ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                {champion_name_sql} AS display_name,
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
                COALESCE(BOOL_AND(pdp.placement IS NOT NULL), FALSE) AS all_placed
            FROM pod_draft_participants pdp
            WHERE pdp.event_id = pde.id
        ) counts ON TRUE
        ORDER BY pde.event_time DESC NULLS LAST;
    """


def _recreate_view(champion_name_sql: str) -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_events;")
    op.execute(_events_view(champion_name_sql))
    op.execute("GRANT SELECT ON public_pod_draft_events TO anon;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
                GRANT SELECT ON public_pod_draft_events TO authenticated;
            END IF;
        END
        $$;
    """)


def upgrade() -> None:
    _recreate_view("COALESCE(p.display_name, pdp.display_name)")


def downgrade() -> None:
    _recreate_view("pdp.display_name")
