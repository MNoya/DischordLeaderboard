"""Add pod_draft_participants.deck_screenshot_url + deck_screenshot_caption

First image attachment a participant posts in the pod thread after the standings embed lands;
captured by the screenshot listener along with the message's text content. The rank-1 champion's
URL is surfaced as the embed image on the announcement and the caption renders italicized above it.

Revision ID: q7g8h9i0j1k2
Revises: p6f7g8h9i0j1
Create Date: 2026-05-16 03:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "q7g8h9i0j1k2"
down_revision: Union[str, None] = "p6f7g8h9i0j1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pod_draft_participants", sa.Column("deck_screenshot_url", sa.String(), nullable=True))
    op.add_column("pod_draft_participants", sa.Column("deck_screenshot_caption", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("pod_draft_participants", "deck_screenshot_caption")
    op.drop_column("pod_draft_participants", "deck_screenshot_url")
