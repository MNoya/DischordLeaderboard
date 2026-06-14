"""Drop the redundant pod participant mainboard columns

mainboard_card_ids and mainboard_cards are superseded by pod_draft_events.draft_log.decks. Run
bot.scripts.backfill_pod_draft_log before applying this so the historical built decks are recovered
into the artifact first; afterwards these columns carry nothing the artifact does not.

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "e5f6g7h8i9j0"
down_revision: Union[str, None] = "d4e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    unbackfilled = op.get_bind().execute(sa.text("""
        SELECT count(*) FROM pod_draft_events WHERE draft_log_gz IS NOT NULL AND draft_log IS NULL
    """)).scalar()
    if unbackfilled:
        raise RuntimeError(
            f"{unbackfilled} event(s) still have draft_log_gz but no draft_log artifact. Run "
            "`python -m bot.scripts.backfill_pod_draft_log` before this migration so the historical "
            "decks in mainboard_card_ids are recovered before the column is dropped."
        )
    op.drop_column("pod_draft_participants", "mainboard_cards")
    op.drop_column("pod_draft_participants", "mainboard_card_ids")


def downgrade() -> None:
    op.add_column("pod_draft_participants", sa.Column("mainboard_card_ids", JSONB(), nullable=True))
    op.add_column("pod_draft_participants", sa.Column("mainboard_cards", JSONB(), nullable=True))
