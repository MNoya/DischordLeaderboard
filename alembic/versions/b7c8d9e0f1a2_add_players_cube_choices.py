"""Add players.cube_choices

The standing cube preference: the server cubes a player marks in the Format Preference picker,
unordered, parallel to flashback_ranking.

Revision ID: b7c8d9e0f1a2
Revises: f9e8d7c6b5a4
Create Date: 2026-07-22 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "f9e8d7c6b5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("cube_choices", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("players", "cube_choices")
