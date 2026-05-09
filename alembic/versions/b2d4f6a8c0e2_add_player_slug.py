"""add player slug

Revision ID: b2d4f6a8c0e2
Revises: a1c2d3e4f5b6
Create Date: 2026-05-09

Adds players.slug — URL-safe handle derived from display_name. Adds the
column nullable=True, backfills every existing row using bot.slug.slugify
(with collision suffixes), then tightens to NOT NULL UNIQUE.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2d4f6a8c0e2"
down_revision: Union[str, None] = "a1c2d3e4f5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("slug", sa.String(), nullable=True))

    # Backfill — pure SQL would need a fancy CTE for collision handling, so
    # iterate in Python instead. Stable order by `id` so reruns produce the
    # same slugs even if rows are inserted between runs.
    from bot.slug import disambiguate_slug, slugify

    bind = op.get_bind()
    rows = list(bind.execute(sa.text(
        "SELECT id, display_name FROM players ORDER BY id"
    )))

    taken: set[str] = set()
    for row in rows:
        base = slugify(row.display_name, row.id)
        chosen = disambiguate_slug(base, taken)
        taken.add(chosen)
        bind.execute(
            sa.text("UPDATE players SET slug = :slug WHERE id = :id"),
            {"slug": chosen, "id": row.id},
        )

    op.alter_column("players", "slug", nullable=False)
    op.create_unique_constraint("uq_players_slug", "players", ["slug"])


def downgrade() -> None:
    op.drop_constraint("uq_players_slug", "players", type_="unique")
    op.drop_column("players", "slug")
