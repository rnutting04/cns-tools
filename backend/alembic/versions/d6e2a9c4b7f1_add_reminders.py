"""add reminders and reminder_deliveries

Revision ID: d6e2a9c4b7f1
Revises: c3d8e6f1a9b2
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d6e2a9c4b7f1"
down_revision: Union[str, Sequence[str], None] = "c3d8e6f1a9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("repeat", sa.String(10), nullable=False),
        sa.Column("lead_days", sa.Integer(), nullable=False),
        sa.Column("send_time", sa.Time(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("next_event_date", sa.Date(), nullable=True),
        sa.Column("next_send_at", sa.DateTime(), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_reminders_next_send_at", "reminders", ["next_send_at"])
    op.create_index("ix_reminders_created_by", "reminders", ["created_by"])

    op.create_table(
        "reminder_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "reminder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reminders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("reminder_id", "event_date", "recipient", name="uq_reminder_delivery"),
    )
    op.create_index(
        "ix_reminder_deliveries_reminder_id", "reminder_deliveries", ["reminder_id"]
    )
    op.create_index("ix_reminder_deliveries_sent_at", "reminder_deliveries", ["sent_at"])


def downgrade() -> None:
    op.drop_index("ix_reminder_deliveries_sent_at", table_name="reminder_deliveries")
    op.drop_index("ix_reminder_deliveries_reminder_id", table_name="reminder_deliveries")
    op.drop_table("reminder_deliveries")
    op.drop_index("ix_reminders_created_by", table_name="reminders")
    op.drop_index("ix_reminders_next_send_at", table_name="reminders")
    op.drop_table("reminders")
