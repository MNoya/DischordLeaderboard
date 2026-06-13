"""Grant authenticated role CRUD on p0p1_entries

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-06-14

RLS policies were in place but the authenticated role lacked table-level
privileges. PostgREST checks GRANTs before RLS, so reads and writes 403'd.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6g7h8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON p0p1_entries TO authenticated;")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON p0p1_entries FROM authenticated;")
