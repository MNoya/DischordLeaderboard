"""Grant authenticated SELECT on public_* views

Revision ID: a1b2c3d4e5f6
Revises: z7s8t9u0v1w2
Create Date: 2026-06-12

Discord OAuth adds Supabase auth sessions. Logged-in users send a JWT, so
PostgREST switches from the anon role to authenticated. Without SELECT grants
on the public_* views, every read 403s for authenticated visitors.

Also sets ALTER DEFAULT PRIVILEGES so future views auto-grant to both roles.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "z7s8t9u0v1w2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PUBLIC_VIEWS = [
    "public_sets",
    "public_leaderboard",
    "public_player_format_breakdown",
    "public_player_draft_events",
    "public_archetype_leaderboard",
    "public_recent_trophies",
    "public_player",
    "public_player_pod_stats",
    "public_pod_scoring",
    "public_pod_draft_replays",
    "public_pod_draft_event_matches",
    "public_pod_draft_events",
    "public_pod_draft_event_participants",
    "public_player_format_archetype_leaderboard",
]


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
                CREATE ROLE authenticated NOLOGIN;
            END IF;
        END
        $$;
    """)
    for view in _PUBLIC_VIEWS:
        op.execute(f"GRANT SELECT ON {view} TO authenticated;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO authenticated;")


def downgrade() -> None:
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM authenticated;")
    for view in _PUBLIC_VIEWS:
        op.execute(f"REVOKE SELECT ON {view} FROM authenticated;")
