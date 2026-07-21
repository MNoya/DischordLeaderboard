"""Add format-interest columns for pod format organization

A standing per-player preference (players.format_interests), the ordered flashback ranking behind it
(players.flashback_ranking, best first), and the interest a signup brings to one slot
(pod_signal_members.format_interest). All additive string arrays defaulting to empty, so existing rows
read as unstated and behave exactly as before; no backfill.

Revision ID: f1a2b3c4d5e6
Revises: i9n0a1m2e3s4
Create Date: 2026-07-20 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "i9n0a1m2e3s4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("format_interests", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "players",
        sa.Column("flashback_ranking", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "pod_signal_members",
        sa.Column("format_interest", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("pod_signal_members", "format_interest")
    op.drop_column("players", "flashback_ranking")
    op.drop_column("players", "format_interests")
