"""Add seating_mode to pod_draft_events

Seats (how the Draftmancer table is arranged) and pairings (how rounds are matched) are orthogonal.
This column records the seats choice — 'random' (default), 'manual', or 'leaderboard' — set pre-session
and surviving restarts. Existing rows backfill to 'random' via the server default; no public view reads it.

Revision ID: s5e4a7m9o2d1
Revises: p0d5c0r3v1w9
Create Date: 2026-06-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "s5e4a7m9o2d1"
down_revision: Union[str, None] = "p0d5c0r3v1w9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pod_draft_events",
        sa.Column("seating_mode", sa.String(), nullable=False, server_default="random"),
    )


def downgrade() -> None:
    op.drop_column("pod_draft_events", "seating_mode")
