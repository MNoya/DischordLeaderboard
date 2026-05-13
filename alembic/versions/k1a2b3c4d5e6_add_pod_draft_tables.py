"""Add pod draft tables

Single-row config table for the event counter, plus events, participants,
and matches. Seeded with event_counter=3 to match the three pod drafts run
on sesh.fyi before the bot took over.

Revision ID: k1a2b3c4d5e6
Revises: j0f1a5b7c2d8
Create Date: 2026-05-13 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "k1a2b3c4d5e6"
down_revision: Union[str, None] = "j0f1a5b7c2d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pod_draft_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_counter", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO pod_draft_config (id, event_counter) VALUES (1, 3)")

    op.create_table(
        "pod_draft_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_number", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("set_id", sa.String(), nullable=True),
        sa.Column("set_code", sa.String(), nullable=False),
        sa.Column("format_label", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("draftmancer_session", sa.String(), nullable=False),
        sa.Column("draftmancer_url", sa.String(), nullable=False),
        sa.Column("discord_thread_id", sa.String(), nullable=False),
        sa.Column("sesh_message_id", sa.String(), nullable=False),
        sa.Column("socket_status", sa.String(), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["set_id"], ["sets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pod_draft_participants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("draftmancer_name", sa.String(), nullable=True),
        sa.Column("placement", sa.Integer(), nullable=True),
        sa.Column("record", sa.String(), nullable=True),
        sa.Column("eliminated_round", sa.Integer(), nullable=True),
        sa.Column("draft_log_url", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["pod_draft_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_pod_participant_event_player",
        "pod_draft_participants",
        ["event_id", "player_id"],
        unique=True,
        postgresql_where=sa.text("player_id IS NOT NULL"),
    )

    op.create_table(
        "pod_draft_matches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("player_a_name", sa.String(), nullable=False),
        sa.Column("player_b_name", sa.String(), nullable=False),
        sa.Column("winner_name", sa.String(), nullable=True),
        sa.Column("score", sa.String(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["pod_draft_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("pod_draft_matches")
    op.drop_index("uq_pod_participant_event_player", table_name="pod_draft_participants")
    op.drop_table("pod_draft_participants")
    op.drop_table("pod_draft_events")
    op.drop_table("pod_draft_config")
