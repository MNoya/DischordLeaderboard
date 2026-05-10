"""Expose seventeenlands_event_id in public_player_draft_events and public_recent_trophies

Revision ID: e5a7b9d2c4f8
Revises: d4f6a8c0e2f4
Create Date: 2026-05-10 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e5a7b9d2c4f8"
down_revision: Union[str, None] = "d4f6a8c0e2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AVATAR_URL_SQL = """
    CASE
        WHEN p.avatar_hash IS NULL OR p.discord_id IS NULL THEN NULL
        ELSE 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    END
"""


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_player_draft_events AS
        SELECT
            p.slug,
            s.code AS set_code,
            de.id AS event_id,
            de.seventeenlands_event_id,
            de.format,
            de.expansion,
            de.wins,
            de.losses,
            de.is_trophy,
            de.colors,
            de.started_at,
            de.finished_at
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE p.active = true;
    """)
    op.execute("GRANT SELECT ON public_player_draft_events TO anon;")

    op.execute(f"""
        CREATE OR REPLACE VIEW public_recent_trophies AS
        SELECT
            s.code AS set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            de.seventeenlands_event_id,
            de.format,
            de.colors,
            de.wins,
            de.losses,
            de.finished_at
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE de.is_trophy = true AND p.active = true
        ORDER BY de.finished_at DESC NULLS LAST;
    """)
    op.execute("GRANT SELECT ON public_recent_trophies TO anon;")


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public_player_draft_events AS
        SELECT
            p.slug,
            s.code AS set_code,
            de.id AS event_id,
            de.format,
            de.expansion,
            de.wins,
            de.losses,
            de.is_trophy,
            de.colors,
            de.started_at,
            de.finished_at
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE p.active = true;
    """)
    op.execute("GRANT SELECT ON public_player_draft_events TO anon;")

    op.execute(f"""
        CREATE OR REPLACE VIEW public_recent_trophies AS
        SELECT
            s.code AS set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            de.format,
            de.colors,
            de.wins,
            de.losses,
            de.finished_at
        FROM draft_events de
        JOIN players p ON p.id = de.player_id
        JOIN sets s ON s.id = de.set_id
        WHERE de.is_trophy = true AND p.active = true
        ORDER BY de.finished_at DESC NULLS LAST;
    """)
    op.execute("GRANT SELECT ON public_recent_trophies TO anon;")
