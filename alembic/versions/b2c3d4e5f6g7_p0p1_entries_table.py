"""Create p0p1_entries table with RLS

Revision ID: b2c3d4e5f6g7
Revises: m1n2o3p4q5r6
Create Date: 2026-06-13

RLS-protected table for the P0P1 voting contest. Each authenticated user
stores up to 9 card picks per set, keyed on (user_id, set_code, slot).
Frontend writes directly via PostgREST; auth.uid() scopes every policy.

Uses IF NOT EXISTS / DROP IF EXISTS so it's safe on Supabase where the
table was already created via a Supabase migration.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, None] = "m1n2o3p4q5r6"
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

            IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'p0p1_entries') THEN
                IF has_auth THEN
                    CREATE TABLE p0p1_entries (
                        user_id    uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                        set_code   text        NOT NULL,
                        slot       text        NOT NULL,
                        card_name  text        NOT NULL,
                        updated_at timestamptz NOT NULL DEFAULT now(),
                        PRIMARY KEY (user_id, set_code, slot)
                    );
                ELSE
                    CREATE TABLE p0p1_entries (
                        user_id    uuid        NOT NULL,
                        set_code   text        NOT NULL,
                        slot       text        NOT NULL,
                        card_name  text        NOT NULL,
                        updated_at timestamptz NOT NULL DEFAULT now(),
                        PRIMARY KEY (user_id, set_code, slot)
                    );
                END IF;
            END IF;

            ALTER TABLE p0p1_entries ENABLE ROW LEVEL SECURITY;

            IF has_auth THEN
                DROP POLICY IF EXISTS "p0p1_entries_select" ON p0p1_entries;
                CREATE POLICY "p0p1_entries_select"
                    ON p0p1_entries FOR SELECT
                    USING (auth.uid() = user_id);

                DROP POLICY IF EXISTS "p0p1_entries_insert" ON p0p1_entries;
                CREATE POLICY "p0p1_entries_insert"
                    ON p0p1_entries FOR INSERT
                    WITH CHECK (auth.uid() = user_id);

                DROP POLICY IF EXISTS "p0p1_entries_update" ON p0p1_entries;
                CREATE POLICY "p0p1_entries_update"
                    ON p0p1_entries FOR UPDATE
                    USING (auth.uid() = user_id)
                    WITH CHECK (auth.uid() = user_id);

                DROP POLICY IF EXISTS "p0p1_entries_delete" ON p0p1_entries;
                CREATE POLICY "p0p1_entries_delete"
                    ON p0p1_entries FOR DELETE
                    USING (auth.uid() = user_id);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS p0p1_entries;")
