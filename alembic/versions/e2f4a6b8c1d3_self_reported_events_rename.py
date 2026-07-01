"""Rename self_reported_trophies to self_reported_events + add is_trophy

/trophy now logs non-trophy decks too, so the table name is broadened to self_reported_events
and an is_trophy flag distinguishes trophies (which rank the MTGO flashback board) from decks
logged for showcase only. Existing rows were all trophies, so is_trophy backfills to true. The
public view is renamed to match.

Revision ID: e2f4a6b8c1d3
Revises: t1r2o3p4h5y6
Create Date: 2026-07-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2f4a6b8c1d3"
down_revision: Union[str, None] = "t1r2o3p4h5y6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def _create_view(table: str, view: str, *, with_is_trophy: bool) -> None:
    is_trophy_col = "t.is_trophy," if with_is_trophy else ""
    op.execute(f"""
        CREATE VIEW {view} AS
        SELECT
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            t.set_code,
            t.record,
            {is_trophy_col}
            t.colors,
            t.platform,
            t.caption,
            t.screenshot_url,
            t.source_channel_id,
            t.source_message_id,
            t.source_url,
            t.reported_at
        FROM {table} t
        JOIN players p ON p.id = t.player_id
        WHERE p.active = true;
    """)
    op.execute(f"GRANT SELECT ON {view} TO anon;")
    op.execute(f"GRANT SELECT ON {view} TO authenticated;")


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_self_reported_trophies;")
    op.rename_table("self_reported_trophies", "self_reported_events")
    op.execute(
        "ALTER TABLE self_reported_events "
        "RENAME CONSTRAINT uq_self_trophy_player_message TO uq_self_event_player_message;"
    )
    op.add_column(
        "self_reported_events",
        sa.Column("is_trophy", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    _create_view("self_reported_events", "public_self_reported_events", with_is_trophy=True)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_self_reported_events;")
    op.drop_column("self_reported_events", "is_trophy")
    op.execute(
        "ALTER TABLE self_reported_events "
        "RENAME CONSTRAINT uq_self_event_player_message TO uq_self_trophy_player_message;"
    )
    op.rename_table("self_reported_events", "self_reported_trophies")
    _create_view("self_reported_trophies", "public_self_reported_trophies", with_is_trophy=False)
