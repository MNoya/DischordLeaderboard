"""Pod signal notify_role + description, pod event description

The /draft launcher can pick which role to notify and attach an optional description to the pod. The
role and description ride the signal so a card re-render keeps them; description also lands on the
event so it survives past the signal.

Revision ID: a7b8c9d0e1f2
Revises: f3g4h5i6j7k8
Create Date: 2026-07-16 06:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f3g4h5i6j7k8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pod_signals", sa.Column("notify_role", sa.String(), nullable=True))
    op.add_column("pod_signals", sa.Column("description", sa.String(), nullable=True))
    op.add_column("pod_draft_events", sa.Column("description", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("pod_draft_events", "description")
    op.drop_column("pod_signals", "description")
    op.drop_column("pod_signals", "notify_role")
