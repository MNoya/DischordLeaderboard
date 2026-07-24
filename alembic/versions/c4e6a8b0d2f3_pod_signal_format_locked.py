"""pod signal format_locked

Revision ID: c4e6a8b0d2f3
Revises: b3d5f7a9c1e2
Create Date: 2026-07-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e6a8b0d2f3'
down_revision: Union[str, None] = 'b3d5f7a9c1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pod_signals',
        sa.Column('format_locked', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE pod_signals SET format_locked = true "
        "WHERE kind = 'queue' OR upper(set_code) IN ('PEASANT', 'SAMP')"
    )


def downgrade() -> None:
    op.drop_column('pod_signals', 'format_locked')
