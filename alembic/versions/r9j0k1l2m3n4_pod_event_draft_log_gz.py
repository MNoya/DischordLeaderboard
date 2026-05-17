"""Add pod_draft_events.draft_log_gz

Gzipped compact-form Draftmancer draft log archive — written on endDraft. Lets us re-derive pick
history later without a 17lands round-trip and keeps the door open for a self-hosted viewer.

Revision ID: r9j0k1l2m3n4
Revises: q7g8h9i0j1k2
Create Date: 2026-05-17 04:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "r9j0k1l2m3n4"
down_revision: Union[str, None] = "q7g8h9i0j1k2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pod_draft_events", sa.Column("draft_log_gz", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("pod_draft_events", "draft_log_gz")
