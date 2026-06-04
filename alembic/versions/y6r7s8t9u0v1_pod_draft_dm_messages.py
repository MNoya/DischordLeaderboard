"""Track DM-side message IDs for pod-draft round pairings + Submit Deck so we can sync edits
across the thread and per-player DMs.

Revision ID: y6r7s8t9u0v1
Revises: x5q6r7s8t9u0
Create Date: 2026-05-18 19:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "y6r7s8t9u0v1"
down_revision: Union[str, None] = "x5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pod_draft_dm_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_id", sa.String(), sa.ForeignKey("pod_draft_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", sa.String(), sa.ForeignKey("pod_draft_participants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("round_num", sa.Integer(), nullable=True),
        sa.Column("match_id", sa.String(), sa.ForeignKey("pod_draft_matches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("dm_channel_id", sa.String(), nullable=False),
        sa.Column("dm_message_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("participant_id", "kind", "round_num", name="uq_pod_dm_msg_participant_kind_round"),
    )
    op.create_index("ix_pod_dm_msg_match_kind", "pod_draft_dm_messages", ["match_id", "kind"])
    op.create_index("ix_pod_dm_msg_event", "pod_draft_dm_messages", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_pod_dm_msg_event", table_name="pod_draft_dm_messages")
    op.drop_index("ix_pod_dm_msg_match_kind", table_name="pod_draft_dm_messages")
    op.drop_table("pod_draft_dm_messages")
