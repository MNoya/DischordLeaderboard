"""Rebuild public_p0p1_ballots off a private voter table, off auth.users

Revision ID: h1v2o3t4e5r6
Revises: g8h9i0j1k2l3
Create Date: 2026-07-16

The API-exposed public_p0p1_ballots view joined auth.users, which trips
Supabase's auth_users_exposed lint (any anon-reachable object referencing
auth.users). Move voter identity into a private public.p0p1_voters table the
definer view reads as owner, so the view no longer touches auth.users.

p0p1_voters carries no anon/authenticated grant and has RLS on with no policy,
so PostgREST can't expose it; only the SECURITY DEFINER view reads it. A
one-time backfill seeds existing voters from auth.users, and a trigger keeps it
synced on every p0p1_entries write so future-set contests need no maintenance.

auth.users only exists on Supabase, so the backfill and trigger are guarded by
a has_auth check; local dev / CI get an empty table and the view over public
tables alone.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "h1v2o3t4e5r6"
down_revision: Union[str, None] = "g8h9i0j1k2l3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE has_auth boolean;
        BEGIN
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth'
            ) INTO has_auth;

            CREATE TABLE IF NOT EXISTS p0p1_voters (
                user_id    uuid PRIMARY KEY,
                name       text NOT NULL,
                avatar_url text
            );
            ALTER TABLE p0p1_voters ENABLE ROW LEVEL SECURITY;

            IF has_auth THEN
                INSERT INTO p0p1_voters (user_id, name, avatar_url)
                SELECT DISTINCT
                    u.id,
                    coalesce(
                        u.raw_user_meta_data->>'user_name',
                        u.raw_user_meta_data->>'full_name',
                        'Anonymous entrant'
                    ),
                    u.raw_user_meta_data->>'avatar_url'
                FROM p0p1_entries e
                JOIN auth.users u ON u.id = e.user_id
                ON CONFLICT (user_id) DO UPDATE
                    SET name = EXCLUDED.name, avatar_url = EXCLUDED.avatar_url;

                CREATE OR REPLACE FUNCTION sync_p0p1_voter()
                RETURNS trigger
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public, auth
                AS $fn$
                BEGIN
                    INSERT INTO public.p0p1_voters (user_id, name, avatar_url)
                    SELECT
                        u.id,
                        coalesce(
                            u.raw_user_meta_data->>'user_name',
                            u.raw_user_meta_data->>'full_name',
                            'Anonymous entrant'
                        ),
                        u.raw_user_meta_data->>'avatar_url'
                    FROM auth.users u
                    WHERE u.id = NEW.user_id
                    ON CONFLICT (user_id) DO UPDATE
                        SET name = EXCLUDED.name, avatar_url = EXCLUDED.avatar_url;
                    RETURN NEW;
                END;
                $fn$;

                DROP TRIGGER IF EXISTS p0p1_entries_sync_voter ON p0p1_entries;
                CREATE TRIGGER p0p1_entries_sync_voter
                    AFTER INSERT OR UPDATE ON p0p1_entries
                    FOR EACH ROW EXECUTE FUNCTION sync_p0p1_voter();
            END IF;
        END $$;
    """)

    op.execute("""
        CREATE OR REPLACE VIEW public_p0p1_ballots AS
        SELECT
            e.set_code,
            dense_rank() OVER (ORDER BY e.user_id)::int AS ballot_id,
            coalesce(v.name, 'Anonymous entrant') AS name,
            v.avatar_url AS avatar_url,
            e.slot,
            e.card_name
        FROM p0p1_entries e
        LEFT JOIN p0p1_voters v ON v.user_id = e.user_id;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                GRANT SELECT ON public_p0p1_ballots TO anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                GRANT SELECT ON public_p0p1_ballots TO authenticated;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS p0p1_entries_sync_voter ON p0p1_entries;")
    op.execute("DROP FUNCTION IF EXISTS sync_p0p1_voter();")
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
            ELSE
                DROP VIEW IF EXISTS public_p0p1_ballots;
            END IF;
        END $$;
    """)
    op.execute("DROP TABLE IF EXISTS p0p1_voters;")
