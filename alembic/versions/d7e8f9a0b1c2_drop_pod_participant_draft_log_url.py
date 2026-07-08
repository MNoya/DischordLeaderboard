"""Drop pod_draft_participants.draft_log_url

The external MagicProTools link was retired in favor of the in-site draft reviewer. Two public views
referenced the column — public_pod_draft_event_participants (dropped) and public_player_draft_events
(pod arm's external_url now NULL) — so both are recreated before the column is dropped.

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-07-03 00:10:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_POD_SLUG_SQL = "trim(both '-' from regexp_replace(lower(pde.name), '[^a-z0-9]+', '-', 'g'))"

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


def _player_events_view_sql(pod_external_url: str) -> str:
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
            (pdp.placement = 1) AS is_trophy,
            COALESCE(pdp.deck_colors, '') AS colors,
            pde.event_time AS started_at,
            pde.event_time AS finished_at,
            NULL::text AS seventeenlands_event_id,
            {pod_external_url} AS external_url,
            pde.name AS event_name,
            {_POD_SLUG_SQL} AS pod_event_slug,
            NULL::text AS end_rank
        FROM pod_draft_participants pdp
        JOIN pod_draft_events pde ON pde.id = pdp.event_id
        JOIN players p ON p.id = pdp.player_id
        WHERE p.active = true
          AND pdp.placement IS NOT NULL;
    """


def _recreate_participants_view(with_draft_log_url: bool) -> None:
    draft_log_col = "pdp.draft_log_url,\n" if with_draft_log_url else ""
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
            {draft_log_col}            pdp.deck_screenshot_url,
            pdp.deck_screenshot_caption,
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
    op.execute(_player_events_view_sql("NULL::text"))
    _grant("public_player_draft_events")
    _recreate_participants_view(with_draft_log_url=False)
    op.drop_column("pod_draft_participants", "draft_log_url")


def downgrade() -> None:
    op.add_column("pod_draft_participants", sa.Column("draft_log_url", sa.String(), nullable=True))
    op.execute(_player_events_view_sql("pdp.draft_log_url"))
    _grant("public_player_draft_events")
    _recreate_participants_view(with_draft_log_url=True)
