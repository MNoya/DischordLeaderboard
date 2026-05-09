"""add player_archetype_scores

Revision ID: c3e5f7b9d1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-05-09

Pre-computed score per (player, set, archetype). Parallels player_set_scores
but partitioned by WUBRG-normalized main-color archetype. Backs the
public_archetype_leaderboard view and the "best UW drafter for SOS" board.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3e5f7b9d1f3"
down_revision: Union[str, None] = "b2d4f6a8c0e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_archetype_scores",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("set_id", sa.String(), nullable=False),
        sa.Column("archetype", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("trophies", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("events", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("wins", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("losses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "last_calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_id"], ["sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "set_id", "archetype", name="uq_player_set_archetype_score"),
    )


def downgrade() -> None:
    op.drop_table("player_archetype_scores")
