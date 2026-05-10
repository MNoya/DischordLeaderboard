"""Allow multiple leaderboard messages per channel/set

Pinned tracked messages stay alongside the latest bottom-fresh tracked message
so both can be kept current by !refresh. The (channel, set) uniqueness no
longer holds.

Revision ID: f6b8c2e0d4a1
Revises: e5a7b9d2c4f8
Create Date: 2026-05-10 19:30:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6b8c2e0d4a1"
down_revision: Union[str, None] = "e5a7b9d2c4f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_leaderboard_message_per_channel_set",
        "leaderboard_messages",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_leaderboard_message_per_channel_set",
        "leaderboard_messages",
        ["channel_id", "set_id"],
    )
