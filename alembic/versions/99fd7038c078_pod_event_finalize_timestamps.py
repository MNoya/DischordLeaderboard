"""pod event finalize timestamps

Revision ID: 99fd7038c078
Revises: c9k2m5p8r1t4
Create Date: 2026-05-30 20:11:27.251674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99fd7038c078'
down_revision: Union[str, None] = 'c9k2m5p8r1t4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pod_draft_events', sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pod_draft_events', sa.Column('championship_posted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('pod_draft_events', 'championship_posted_at')
    op.drop_column('pod_draft_events', 'finalized_at')
