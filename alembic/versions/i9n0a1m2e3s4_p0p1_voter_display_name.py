"""Use the Discord display name for p0p1 voters, not the raw handle

Revision ID: i9n0a1m2e3s4
Revises: h1v2o3t4e5r6
Create Date: 2026-07-19

p0p1_voters.name was backfilled and synced from user_name (the @handle, e.g.
m.noya). Prefer the Discord display name instead — custom_claims.global_name,
then full_name / name — matching the frontend AuthContext, with the handle only
as a last resort. Re-backfills existing rows and rewrites the sync trigger.
Supabase-only; the has_auth guard makes it a no-op on local dev / CI.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "i9n0a1m2e3s4"
down_revision: Union[str, None] = "h1v2o3t4e5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DISPLAY_NAME = """coalesce(
    nullif(u.raw_user_meta_data->'custom_claims'->>'global_name', ''),
    nullif(u.raw_user_meta_data->>'full_name', ''),
    nullif(u.raw_user_meta_data->>'user_name', ''),
    'Anonymous entrant'
)"""

HANDLE_NAME = """coalesce(
    u.raw_user_meta_data->>'user_name',
    u.raw_user_meta_data->>'full_name',
    'Anonymous entrant'
)"""


def _rewrite(name_expr: str) -> None:
    op.execute(f"""
        DO $$
        DECLARE has_auth boolean;
        BEGIN
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth'
            ) INTO has_auth;

            IF has_auth THEN
                UPDATE p0p1_voters v
                SET name = {name_expr}
                FROM auth.users u
                WHERE u.id = v.user_id;

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
                        {name_expr},
                        u.raw_user_meta_data->>'avatar_url'
                    FROM auth.users u
                    WHERE u.id = NEW.user_id
                    ON CONFLICT (user_id) DO UPDATE
                        SET name = EXCLUDED.name, avatar_url = EXCLUDED.avatar_url;
                    RETURN NEW;
                END;
                $fn$;
            END IF;
        END $$;
    """)


def upgrade() -> None:
    _rewrite(DISPLAY_NAME)


def downgrade() -> None:
    _rewrite(HANDLE_NAME)
