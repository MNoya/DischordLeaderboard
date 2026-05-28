"""Surface pod_event_slug in public_player_draft_events

Adds a pod_event_slug column so the player profile event log can link pod-draft
rows to /pods/<slug>. NULL on the 17lands arm.

Revision ID: t2p0d3s5l7n9
Revises: s1c0r3t5b7l9
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op


revision: str = "t2p0d3s5l7n9"
down_revision: Union[str, None] = "s1c0r3t5b7l9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_POD_SLUG_SQL = "trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g'))"


def _view_sql(pod_slug_17l: str, pod_slug_pod: str) -> str:
    return f"""
        CREATE OR REPLACE VIEW public_player_draft_events AS
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
            END AS external_url,
            NULL::text AS event_name{pod_slug_17l}
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
            COALESCE(pdp.deck_colors, '') AS colors,
            pde.event_time AS started_at,
            pde.event_time AS finished_at,
            NULL::text AS seventeenlands_event_id,
            pdp.draft_log_url AS external_url,
            pde.name AS event_name{pod_slug_pod}
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND pdp.placement IS NOT NULL;
    """


def upgrade() -> None:
    op.execute(_view_sql(",\n            NULL::text AS pod_event_slug", f",\n            {_POD_SLUG_SQL} AS pod_event_slug"))
    op.execute("GRANT SELECT ON public_player_draft_events TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_draft_events;")
    op.execute(_view_sql("", ""))
    op.execute("GRANT SELECT ON public_player_draft_events TO anon;")
