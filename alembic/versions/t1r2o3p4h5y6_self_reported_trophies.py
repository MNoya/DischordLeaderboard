"""Add self_reported_trophies table + public view

Self-reported trophies logged via /trophy from trophy-hype posts. Showcase only —
never scored. The public_self_reported_trophies view exposes them per (slug, set_code)
for the profile trophy-case band, mirroring public_pod_scoring's avatar build and the
active-only (never opt-in) gating pods use.

Revision ID: t1r2o3p4h5y6
Revises: c5d9f1a3b7e2
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "t1r2o3p4h5y6"
down_revision: Union[str, None] = "c5d9f1a3b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def upgrade() -> None:
    op.create_table(
        "self_reported_trophies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("set_id", sa.String(), nullable=True),
        sa.Column("set_code", sa.String(), nullable=False),
        sa.Column("record", sa.String(), nullable=False),
        sa.Column("colors", sa.String(), nullable=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("screenshot_url", sa.String(), nullable=True),
        sa.Column("source_channel_id", sa.String(), nullable=False),
        sa.Column("source_message_id", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_id"], ["sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "source_message_id", name="uq_self_trophy_player_message"),
    )
    op.execute(f"""
        CREATE VIEW public_self_reported_trophies AS
        SELECT
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            t.set_code,
            t.record,
            t.colors,
            t.platform,
            t.caption,
            t.screenshot_url,
            t.source_channel_id,
            t.source_message_id,
            t.source_url,
            t.reported_at
        FROM self_reported_trophies t
        JOIN players p ON p.id = t.player_id
        WHERE p.active = true;
    """)
    op.execute("GRANT SELECT ON public_self_reported_trophies TO anon;")
    op.execute("GRANT SELECT ON public_self_reported_trophies TO authenticated;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_self_reported_trophies;")
    op.drop_table("self_reported_trophies")
