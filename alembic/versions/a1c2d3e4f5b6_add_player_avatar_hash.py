"""add player avatar_hash

Revision ID: a1c2d3e4f5b6
Revises: e8c3a1b2f0d4
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1c2d3e4f5b6"
down_revision: Union[str, None] = "e8c3a1b2f0d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("avatar_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "avatar_hash")
