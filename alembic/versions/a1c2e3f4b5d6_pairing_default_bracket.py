"""Default new pod-draft events to the Fast Bracket pairing mode instead of Swiss. Non-8 rosters still
fall back to Swiss at start, so this only changes the common 8-player case.

Revision ID: a1c2e3f4b5d6
Revises: f7g8h9i0j1k2
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1c2e3f4b5d6"
down_revision: Union[str, None] = "f7g8h9i0j1k2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("pod_draft_events", "pairing_mode", server_default="bracket")


def downgrade() -> None:
    op.alter_column("pod_draft_events", "pairing_mode", server_default="swiss")
