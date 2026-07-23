"""Show team pods in public_player_draft_events

Team drafts leave placement NULL and carry the result on team + record, so the pod arm's
`placement IS NOT NULL` filter dropped every team-draft participation from a player's profile events,
and `is_trophy = placement = 1` never fired on a team 3-0. The arm now admits any finalized seat
(placement or record present) and treats a 3-0 record as a trophy, matching the pod scoring rule.

Revision ID: b3d5f7a9c1e2
Revises: acdd57812f62
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b3d5f7a9c1e2"
down_revision: Union[str, None] = "acdd57812f62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_POD_SLUG_SQL = "trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g'))"


def _player_events_view_sql(pod_is_trophy: str, pod_where: str) -> str:
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
            NULL::text AS event_name,
            NULL::text AS pod_event_slug,
            de.end_rank
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
            {pod_is_trophy} AS is_trophy,
            COALESCE(pdp.deck_colors, '') AS colors,
            pde.event_time AS started_at,
            pde.event_time AS finished_at,
            NULL::text AS seventeenlands_event_id,
            NULL::text AS external_url,
            pde.name AS event_name,
            {_POD_SLUG_SQL} AS pod_event_slug,
            NULL::text AS end_rank
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND {pod_where};
    """


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
    op.execute(_player_events_view_sql(
        "(pdp.placement = 1 OR pdp.record = '3-0')",
        "(pdp.placement IS NOT NULL OR pdp.record IS NOT NULL)",
    ))
    _grant("public_player_draft_events")


def downgrade() -> None:
    op.execute(_player_events_view_sql(
        "(pdp.placement = 1)",
        "pdp.placement IS NOT NULL",
    ))
    _grant("public_player_draft_events")
