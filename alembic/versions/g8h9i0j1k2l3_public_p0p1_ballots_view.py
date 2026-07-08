"""Add public_p0p1_ballots view

Revision ID: g8h9i0j1k2l3
Revises: f3a5c7e9b2d4
Create Date: 2026-06-27

Every voter's (slot, card_name) rows for the P0P1 contest, with a display
identity denormalized from auth.users raw_user_meta_data. View bypasses RLS
(runs as owner), same pattern as public_p0p1_pick_stats.

No time gate — voting is closed. No complete-entrants filter — partial ballots
are included and sink naturally via partial GIHWR sum at scoring time.

Voter identity: name from raw_user_meta_data ('user_name' / 'full_name'),
avatar_url ready-to-use from Discord CDN. Never exposes auth.users.id (UUID)
or email. ballot_id is a dense_rank over user_id — opaque, stable within a
fetch, non-identifying.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, None] = "f3a5c7e9b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # auth.users only exists on Supabase, not in local dev / CI plain Postgres.
    # Mirror the pattern from b2c3d4e5f6g7 — skip the view when auth is absent.
    op.execute("""
        DO $$
        DECLARE has_auth boolean;
        BEGIN
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth'
            ) INTO has_auth;

            IF has_auth THEN
                CREATE OR REPLACE VIEW public_p0p1_ballots AS
                SELECT
                    e.set_code,
                    dense_rank() OVER (ORDER BY e.user_id)::int AS ballot_id,
                    coalesce(
                        u.raw_user_meta_data->>'user_name',
                        u.raw_user_meta_data->>'full_name',
                        'Anonymous entrant'
                    ) AS name,
                    u.raw_user_meta_data->>'avatar_url' AS avatar_url,
                    e.slot,
                    e.card_name
                FROM p0p1_entries e
                JOIN auth.users u ON u.id = e.user_id;

                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    GRANT SELECT ON public_p0p1_ballots TO anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    GRANT SELECT ON public_p0p1_ballots TO authenticated;
                END IF;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_p0p1_ballots;")
