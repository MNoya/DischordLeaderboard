"""Add pod_draft_participants.mainboard_card_ids

Stores the post-draft mainboard as a list of Draftmancer card IDs (keys into the
draft log's carddata). Sideboard is derived at read time from the seat's pool in
draft_log_gz minus this mainboard. Populated only when Draftmancer's per-user
decklist is present in the log (i.e., player used Draftmancer's deck builder);
left NULL otherwise.

Revision ID: f3a4b5c6d7e8
Revises: e2x3y4z5a6b7
Create Date: 2026-05-21 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pod_draft_participants",
        sa.Column("mainboard_card_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pod_draft_participants", "mainboard_card_ids")
