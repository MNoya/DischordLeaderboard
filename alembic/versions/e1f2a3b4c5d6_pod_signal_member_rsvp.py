"""Add pod_signal_members.rsvp, pod_draft_events.discord_scheduled_event_id, pod_signals RSVP + preset columns

Revision ID: e1f2a3b4c5d6
Revises: d8ffcbcda5ba
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd8ffcbcda5ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pod_signal_members', sa.Column('rsvp', sa.String(), server_default='yes', nullable=False))
    op.add_column('pod_signals', sa.Column('thread_message_id', sa.String(), nullable=True))
    op.add_column('pod_signals', sa.Column('set_code', sa.String(), nullable=True))
    op.add_column('pod_signals', sa.Column('pairing_mode', sa.String(), nullable=True))
    op.add_column('pod_signals', sa.Column('seating_mode', sa.String(), nullable=True))
    op.add_column('pod_signals', sa.Column('pick_timer', sa.Integer(), nullable=True))
    op.add_column('pod_draft_events', sa.Column('discord_scheduled_event_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('pod_draft_events', 'discord_scheduled_event_id')
    op.drop_column('pod_signals', 'pick_timer')
    op.drop_column('pod_signals', 'seating_mode')
    op.drop_column('pod_signals', 'pairing_mode')
    op.drop_column('pod_signals', 'set_code')
    op.drop_column('pod_signals', 'thread_message_id')
    op.drop_column('pod_signal_members', 'rsvp')
