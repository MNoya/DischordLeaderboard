"""draft_events.set_id nullable — persist unrouted drafts

Drafts in expansions we haven't registered yet (e.g. a set 17lands ships before
we add it to ``bot/sets.py``) used to get dropped at ingest. Make ``set_id``
nullable so we persist every draft 17lands returns; ``/add-set`` then claims
the orphans (sets ``set_id`` on matching rows) and rebuilds aggregates.

Revision ID: e2x3y4z5a6b7
Revises: d1w2x3y4z5a6
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e2x3y4z5a6b7"
down_revision: Union[str, None] = "d1w2x3y4z5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("draft_events", "set_id", nullable=True)


def downgrade() -> None:
    # Downgrade requires deleting orphan rows first since the constraint won't accept NULLs
    op.execute("DELETE FROM draft_events WHERE set_id IS NULL;")
    op.alter_column("draft_events", "set_id", nullable=False)
