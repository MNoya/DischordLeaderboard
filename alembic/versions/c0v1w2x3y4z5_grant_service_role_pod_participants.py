"""Grant service_role SELECT/UPDATE on pod_draft_participants

The refresh-deck-url Edge Function needs to read deck_screenshot_url and write
back the refreshed value via the service_role JWT. New Supabase projects no
longer grant service_role full access on public.* tables by default.

Revision ID: c0v1w2x3y4z5
Revises: b9u0v1w2x3y4
Create Date: 2026-05-19 18:50:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c0v1w2x3y4z5"
down_revision: Union[str, None] = "b9u0v1w2x3y4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
                CREATE ROLE service_role NOLOGIN;
            END IF;
        END
        $$;
    """)
    op.execute("GRANT SELECT, UPDATE ON public.pod_draft_participants TO service_role;")


def downgrade() -> None:
    op.execute("REVOKE SELECT, UPDATE ON public.pod_draft_participants FROM service_role;")
