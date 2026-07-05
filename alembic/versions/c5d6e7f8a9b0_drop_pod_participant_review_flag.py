"""Drop pod_draft_participants.wants_draft_review

The pre-commit "stay for draft review" opt-in was replaced by an at-review-time 🙋 reaction on the
/pod-review announcement, so the column has no readers or writers left.

Revision ID: c5d6e7f8a9b0
Revises: b3t7r9o1p5h2
Create Date: 2026-07-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b3t7r9o1p5h2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("pod_draft_participants", "wants_draft_review")


def downgrade() -> None:
    op.add_column(
        "pod_draft_participants",
        sa.Column("wants_draft_review", sa.Boolean(), nullable=True),
    )
