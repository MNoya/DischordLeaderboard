"""Add pod_draft_participants.wants_draft_review

Three-state flag: NULL = never answered, TRUE = staying for group draft-log review,
FALSE = explicitly declined. Toggled on the Submit Deck ephemeral.

Revision ID: t1m2n3o4p5q6
Revises: r9j0k1l2m3n4
Create Date: 2026-05-17 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "t1m2n3o4p5q6"
down_revision: Union[str, None] = "r9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pod_draft_participants",
        sa.Column("wants_draft_review", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pod_draft_participants", "wants_draft_review")
