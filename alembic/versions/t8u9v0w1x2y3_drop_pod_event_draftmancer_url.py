"""Drop pod_draft_events.draftmancer_url; the link is composed from settings at send time

Revision ID: t8u9v0w1x2y3
Revises: s5e4a7m9o2d1
Create Date: 2026-06-06 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "t8u9v0w1x2y3"
down_revision: Union[str, None] = "s5e4a7m9o2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("pod_draft_events", "draftmancer_url")


def downgrade() -> None:
    op.add_column("pod_draft_events", sa.Column("draftmancer_url", sa.String(), nullable=True))
    op.execute(
        "UPDATE pod_draft_events SET draftmancer_url = 'https://draftmancer.com/?session=' || draftmancer_session"
    )
    op.alter_column("pod_draft_events", "draftmancer_url", nullable=False)
