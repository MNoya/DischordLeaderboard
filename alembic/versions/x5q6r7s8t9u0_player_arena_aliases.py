"""Add players.arena_aliases for multi-account pod-draft matching

Revision ID: x5q6r7s8t9u0
Revises: w4p5q6r7s8t9
Create Date: 2026-05-18 17:40:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "x5q6r7s8t9u0"
down_revision: Union[str, None] = "w4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column(
            "arena_aliases",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.execute(
        r"""
        UPDATE players
        SET arena_aliases = ARRAY[lower(regexp_replace(arena_name, '#\d+$', ''))]
        WHERE arena_name IS NOT NULL AND arena_name <> ''
        """
    )


def downgrade() -> None:
    op.drop_column("players", "arena_aliases")
