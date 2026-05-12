"""Add player_format_archetype_scores + public view

Backs the combined format+colors leaderboard. Mirrors player_archetype_scores
but adds a format_label dimension matching public_player_format_breakdown.

Revision ID: i9e1f5b3a7d4
Revises: h8d0e4a2f6c3
Create Date: 2026-05-12 02:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "i9e1f5b3a7d4"
down_revision: Union[str, None] = "h8d0e4a2f6c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = (
    "CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL "
    "THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128' "
    "ELSE NULL END"
)


def upgrade() -> None:
    op.create_table(
        "player_format_archetype_scores",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("set_id", sa.String(), nullable=False),
        sa.Column("format_label", sa.String(), nullable=False),
        sa.Column("archetype", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("trophies", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("events", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("wins", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("losses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "last_calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_id"], ["sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id", "set_id", "format_label", "archetype",
            name="uq_player_set_format_label_archetype_score",
        ),
    )
    op.create_index(
        "ix_pfas_set_format_archetype",
        "player_format_archetype_scores",
        ["set_id", "format_label", "archetype"],
    )

    op.execute(f"""
        CREATE OR REPLACE VIEW public_player_format_archetype_leaderboard AS
        SELECT
            s.code AS set_code,
            pfas.format_label,
            pfas.archetype,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            RANK() OVER (
                PARTITION BY s.code, pfas.format_label, pfas.archetype
                ORDER BY pfas.score DESC,
                         (pfas.wins::numeric / NULLIF(pfas.wins + pfas.losses, 0)) DESC
            )::int AS rank,
            pfas.score::numeric AS score,
            pfas.trophies,
            pfas.events,
            pfas.wins,
            pfas.losses,
            pfas.last_calculated_at
        FROM player_format_archetype_scores pfas
        JOIN players p ON p.id = pfas.player_id
        JOIN sets s ON s.id = pfas.set_id
        WHERE p.active = true;
    """)
    op.execute("GRANT SELECT ON public_player_format_archetype_leaderboard TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_format_archetype_leaderboard;")
    op.drop_index("ix_pfas_set_format_archetype", table_name="player_format_archetype_scores")
    op.drop_table("player_format_archetype_scores")
