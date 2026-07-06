"""Add format to self_reported_events + expose it on the public view

/trophy now records the draft format (Premier / Traditional / Single Elim / write-in) so an MTGO
single-elim 3-0 no longer mislabels as Trad Draft. Nullable so rows logged before the field
existed keep rendering with the record-derived guess.

Revision ID: f3a5c7e9b2d4
Revises: d7e8f9a0b1c2
Create Date: 2026-07-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f3a5c7e9b2d4"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def _create_view(*, with_format: bool) -> None:
    format_col = "t.format," if with_format else ""
    op.execute(f"""
        CREATE VIEW public_self_reported_events AS
        SELECT
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            t.set_code,
            t.record,
            t.is_trophy,
            t.colors,
            t.platform,
            {format_col}
            t.caption,
            t.screenshot_url,
            t.source_channel_id,
            t.source_message_id,
            t.source_url,
            t.reported_at
        FROM self_reported_events t
        JOIN players p ON p.id = t.player_id
        WHERE p.active = true;
    """)
    op.execute("GRANT SELECT ON public_self_reported_events TO anon;")
    op.execute("GRANT SELECT ON public_self_reported_events TO authenticated;")


def upgrade() -> None:
    op.add_column("self_reported_events", sa.Column("format", sa.String(), nullable=True))
    op.execute("DROP VIEW IF EXISTS public_self_reported_events;")
    _create_view(with_format=True)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_self_reported_events;")
    op.drop_column("self_reported_events", "format")
    _create_view(with_format=False)
