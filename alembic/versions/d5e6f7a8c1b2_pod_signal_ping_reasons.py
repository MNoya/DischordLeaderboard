"""Split pod_signals.nudged_at into the two recruiting ping reasons

A signal can push at most one one-more ping (the queue's one-short-of-firing nudge) and one last-call
ping (the T-1h close-to-the-aim rally). Renaming keeps the queue's already-spent nudges spent.

Revision ID: d5e6f7a8c1b2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-21 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d5e6f7a8c1b2"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("pod_signals", "nudged_at", new_column_name="one_more_pinged_at")
    op.add_column("pod_signals", sa.Column("last_call_pinged_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("pod_signals", "last_call_pinged_at")
    op.alter_column("pod_signals", "one_more_pinged_at", new_column_name="nudged_at")
