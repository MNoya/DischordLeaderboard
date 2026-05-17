"""Add public_pod_draft_replays + public_pod_draft_event_matches views

Revision ID: v3o4p5q6r7s8
Revises: u2n3o4p5q6r7
Create Date: 2026-05-17 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "v3o4p5q6r7s8"
down_revision: Union[str, None] = "u2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE VIEW public_pod_draft_replays AS
        SELECT
            pdr.event_id,
            pde.name AS event_name,
            pde.event_date,
            pde.set_code,
            pdr.player_id,
            p.slug AS player_slug,
            p.display_name AS player_display_name,
            pdr.game_id,
            pdr.link,
            pdr.game_time,
            pdr.won,
            pdr.turns,
            pdr.on_play,
            pdr.inferred_round
        FROM pod_draft_replays pdr
        JOIN pod_draft_events pde ON pde.id = pdr.event_id
        JOIN players p ON p.id = pdr.player_id;
    """)
    op.execute("GRANT SELECT ON public_pod_draft_replays TO anon;")

    op.execute("""
        CREATE VIEW public_pod_draft_event_matches AS
        SELECT
            pde.id AS event_id,
            pde.name AS event_name,
            pdm.round,
            pdm.player_a_name,
            pdm.player_b_name,
            pdm.winner_name,
            pdm.score,
            pdm.reported_at
        FROM pod_draft_matches pdm
        JOIN pod_draft_events pde ON pde.id = pdm.event_id;
    """)
    op.execute("GRANT SELECT ON public_pod_draft_event_matches TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_pod_draft_event_matches;")
    op.execute("DROP VIEW IF EXISTS public_pod_draft_replays;")
