"""Drop pod_draft event_number and the counter table

Event identity is name + event_date going forward; the auto-incrementing
event_number was unused by user-facing surfaces and added friction for sesh
events that didn't include #N in the title.

Revision ID: l2b3c4d5e6f7
Revises: k1a2b3c4d5e6
Create Date: 2026-05-13 19:35:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "l2b3c4d5e6f7"
down_revision: Union[str, None] = "k1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("pod_draft_events", "event_number")
    op.drop_table("pod_draft_config")


def downgrade() -> None:
    op.create_table(
        "pod_draft_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_counter", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO pod_draft_config (id, event_counter) VALUES (1, 0)")
    op.add_column("pod_draft_events", sa.Column("event_number", sa.Integer(), nullable=True))
