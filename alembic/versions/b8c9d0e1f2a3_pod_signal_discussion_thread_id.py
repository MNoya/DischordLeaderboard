"""Pod signal discussion_thread_id

The queue's discussion thread is now a standalone channel thread rather than one hung off the card
message, so its id no longer equals the card message id and has to be tracked to add joiners to it.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-16 07:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pod_signals", sa.Column("discussion_thread_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("pod_signals", "discussion_thread_id")
