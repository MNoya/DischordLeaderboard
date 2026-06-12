"""Grant authenticated SELECT on public_* views

Revision ID: a1b2c3d4e5f6
Revises: e6n7p8q9r0s1
Create Date: 2026-06-12

Discord OAuth adds Supabase auth sessions. Logged-in users send a JWT, so
PostgREST switches from the anon role to authenticated. Without SELECT grants
on the public_* views, every read 403s for authenticated visitors.

Grants are scoped to the curated public_* views only, matching the anon role.
Raw tables stay unreadable so future tables are not exposed by default.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e6n7p8q9r0s1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PUBLIC_VIEWS = [
    "public_sets",
    "public_leaderboard",
    "public_player_format_breakdown",
    "public_player_draft_events",
    "public_recent_trophies",
    "public_player",
    "public_player_pod_stats",
    "public_pod_scoring",
    "public_pod_draft_replays",
    "public_pod_draft_event_matches",
    "public_pod_draft_events",
    "public_pod_draft_event_participants",
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


def downgrade() -> None:
    for view in _PUBLIC_VIEWS:
        op.execute(f"REVOKE SELECT ON {view} FROM authenticated;")
