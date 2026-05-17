"""Add pod_draft_replays table

Revision ID: u2n3o4p5q6r7
Revises: t1m2n3o4p5q6
Create Date: 2026-05-17 14:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "u2n3o4p5q6r7"
down_revision: Union[str, None] = "t1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pod_draft_replays",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_id", sa.String(), sa.ForeignKey("pod_draft_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.String(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("link", sa.String(), nullable=False),
        sa.Column("game_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("won", sa.Boolean(), nullable=False),
        sa.Column("turns", sa.Integer(), nullable=True),
        sa.Column("on_play", sa.Boolean(), nullable=True),
        sa.Column("inferred_round", sa.Integer(), nullable=True),
        sa.UniqueConstraint("event_id", "player_id", "game_id", name="uq_pod_draft_replay_event_player_game"),
    )
    op.create_index(
        "ix_pod_draft_replays_event_player",
        "pod_draft_replays",
        ["event_id", "player_id"],
    )
    op.create_index(
        "ix_pod_draft_replays_event_time",
        "pod_draft_replays",
        ["event_id", "game_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_pod_draft_replays_event_time", table_name="pod_draft_replays")
    op.drop_index("ix_pod_draft_replays_event_player", table_name="pod_draft_replays")
    op.drop_table("pod_draft_replays")
