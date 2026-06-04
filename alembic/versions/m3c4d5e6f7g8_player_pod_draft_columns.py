"""Player schema changes for pod-draft-capable users

Adds arena_name for `/pod-link-arena`.
Drops the redundant seventeenlands_url column (pure denormalization of
`https://www.17lands.com/user_history/{token}`, never read).
Makes seventeenlands_token nullable so pod-draft-only players can exist without a 17lands profile.
Backfills any pre-existing NULL discord_id rows with `seed-{slug}` placeholders before tightening
discord_id to NOT NULL.

Revision ID: m3c4d5e6f7g8
Revises: l2b3c4d5e6f7
Create Date: 2026-05-14 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "m3c4d5e6f7g8"
down_revision: Union[str, None] = "l2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("arena_name", sa.String(), nullable=True))
    op.drop_column("players", "seventeenlands_url")
    op.alter_column("players", "seventeenlands_token", nullable=True)
    op.execute("UPDATE players SET discord_id = 'seed-' || slug WHERE discord_id IS NULL")
    op.alter_column("players", "discord_id", nullable=False)


def downgrade() -> None:
    op.alter_column("players", "discord_id", nullable=True)
    op.alter_column("players", "seventeenlands_token", nullable=False)
    op.add_column("players", sa.Column("seventeenlands_url", sa.String(), nullable=True))
    op.execute(
        "UPDATE players SET seventeenlands_url = 'https://www.17lands.com/user_history/' || seventeenlands_token"
    )
    op.alter_column("players", "seventeenlands_url", nullable=False)
    op.drop_column("players", "arena_name")
