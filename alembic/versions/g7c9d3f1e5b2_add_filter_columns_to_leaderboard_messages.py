"""Add filter_type / filter_value to leaderboard_messages

Lets the bot track filtered leaderboard posts (format:Premier, color:Boros)
alongside unfiltered ones so !refresh can re-render each with the right data.

Revision ID: g7c9d3f1e5b2
Revises: f6b8c2e0d4a1
Create Date: 2026-05-10 19:45:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "g7c9d3f1e5b2"
down_revision: Union[str, None] = "f6b8c2e0d4a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leaderboard_messages",
        sa.Column("filter_type", sa.String(), nullable=True),
    )
    op.add_column(
        "leaderboard_messages",
        sa.Column("filter_value", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leaderboard_messages", "filter_value")
    op.drop_column("leaderboard_messages", "filter_type")
