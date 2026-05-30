"""Add pairing_mode to pod_draft_events

Pods can run either the Swiss pairer (whole-round, the default) or the fast-advance bracket pairer.
The mode is fixed for a pod's lifetime, so it lives on the event row. Existing rows backfill to
'swiss' via the server default; no public view reads this column.

Revision ID: c9k2m5p8r1t4
Revises: u3q1e4t6m8o0
Create Date: 2026-05-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9k2m5p8r1t4"
down_revision: Union[str, None] = "u3q1e4t6m8o0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pod_draft_events",
        sa.Column("pairing_mode", sa.String(), nullable=False, server_default="swiss"),
    )


def downgrade() -> None:
    op.drop_column("pod_draft_events", "pairing_mode")
