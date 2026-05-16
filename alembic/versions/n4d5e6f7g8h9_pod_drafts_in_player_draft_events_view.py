"""Include pod draft participations in public_player_draft_events

UNION ALL of two arms — the existing draft_events stream and finalized
pod_draft_participants. Pod rows carry format='PodDraft', empty colors,
wins/losses parsed from the record string, and is_trophy = (placement = 1).
Adds external_url so the frontend can link both event kinds with the same
column (17lands deck URL for 17L rows, draft_log_url for pod rows).

Revision ID: n4d5e6f7g8h9
Revises: m3c4d5e6f7g8
Create Date: 2026-05-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "n4d5e6f7g8h9"
down_revision: Union[str, None] = "m3c4d5e6f7g8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_draft_events;")
    op.execute("""
        CREATE VIEW public_player_draft_events AS
        SELECT
            p.slug,
            s.code AS set_code,
            de.id AS event_id,
            de.format,
            de.expansion,
            de.wins,
            de.losses,
            de.is_trophy,
            de.colors,
            de.started_at,
            de.finished_at,
            de.seventeenlands_event_id,
            CASE
                WHEN de.seventeenlands_event_id IS NOT NULL
                    THEN 'https://www.17lands.com/deck/' || de.seventeenlands_event_id
                ELSE NULL
            END AS external_url
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE p.active = true

        UNION ALL

        SELECT
            p.slug,
            pde.set_code,
            pdp.id AS event_id,
            'PodDraft' AS format,
            pde.set_code AS expansion,
            COALESCE(NULLIF(split_part(pdp.record, '-', 1), ''), '0')::int AS wins,
            COALESCE(NULLIF(split_part(pdp.record, '-', 2), ''), '0')::int AS losses,
            (pdp.placement = 1) AS is_trophy,
            '' AS colors,
            pde.event_time AS started_at,
            pde.event_time AS finished_at,
            NULL::text AS seventeenlands_event_id,
            pdp.draft_log_url AS external_url
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND pdp.placement IS NOT NULL;
    """)
    op.execute("GRANT SELECT ON public_player_draft_events TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_draft_events;")
    op.execute("""
        CREATE VIEW public_player_draft_events AS
        SELECT
            p.slug,
            s.code AS set_code,
            de.id AS event_id,
            de.format,
            de.expansion,
            de.wins,
            de.losses,
            de.is_trophy,
            de.colors,
            de.started_at,
            de.finished_at,
            de.seventeenlands_event_id
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE p.active = true;
    """)
    op.execute("GRANT SELECT ON public_player_draft_events TO anon;")
