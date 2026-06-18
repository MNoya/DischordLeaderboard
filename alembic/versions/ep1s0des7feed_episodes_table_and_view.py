"""Episodes table + public_episodes view: DB-synced podcast/YouTube media feed

One row per published piece of content — podcast episode, YouTube video, or both when a
video matches its episode. Category and set come from the channel's curated playlists
(synced bot-side), so the frontend stops merging Libsyn + YouTube in the browser and just
reads the curated rows. The view exposes display columns only.

Revision ID: ep1s0des7feed
Revises: c1u2b3e4s5n6
Create Date: 2026-06-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "ep1s0des7feed"
down_revision: Union[str, None] = "c1u2b3e4s5n6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "episodes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("guid", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("link", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("audio_url", sa.String(), nullable=True),
        sa.Column("youtube_id", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("set_code", sa.String(), nullable=True),
        sa.Column("set_name", sa.String(), nullable=True),
        sa.Column("set_released_at", sa.Date(), nullable=True),
        sa.Column("playlists", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guid", name="uq_episodes_guid"),
    )
    op.create_index("ix_episodes_published_at", "episodes", ["published_at"])
    op.create_index("ix_episodes_set_code", "episodes", ["set_code"])

    op.execute("""
        CREATE OR REPLACE VIEW public_episodes AS
        SELECT
            id,
            guid,
            kind,
            number,
            title,
            link,
            summary,
            image,
            published_at,
            duration_seconds,
            audio_url,
            youtube_id,
            category,
            set_code,
            set_name,
            set_released_at
        FROM episodes
        ORDER BY published_at DESC;
    """)

    _grant_if_exists("public_episodes", "GRANT SELECT ON public.%s TO anon;")
    _grant_if_exists("public_episodes", "GRANT SELECT ON public.%s TO authenticated;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_episodes;")
    op.drop_index("ix_episodes_set_code", table_name="episodes")
    op.drop_index("ix_episodes_published_at", table_name="episodes")
    op.drop_table("episodes")


def _grant_if_exists(view: str, statement: str) -> None:
    op.execute(f"""
        DO $$
        BEGIN
            IF to_regclass('public.{view}') IS NOT NULL THEN
                EXECUTE format('{statement}', '{view}');
            END IF;
        END
        $$;
    """)
