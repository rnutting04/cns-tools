"""set null on budget_layout_profiles.confirmed_by when a user is deleted

Revision ID: b5e8d2c47f16
Revises: a7d9c3f1b204
Create Date: 2026-11-07

A layout profile is keyed by workbook signature, not by the person who signed
it off, and it outlives any individual account — so the confirmer reference has
no business pinning a user row in place. With the default RESTRICT, deleting a
user who had ever confirmed a layout failed with a foreign key violation, which
the users router surfaced as "User has associated jobs or data and cannot be
deleted" — misleading, since the blocker was a layout profile rather than their
work. This matches the behaviour audit_events.actor_user_id already has: keep
the record, forget who it pointed at.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "b5e8d2c47f16"
down_revision: Union[str, Sequence[str], None] = "a7d9c3f1b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT = "budget_layout_profiles_confirmed_by_fkey"
TABLE = "budget_layout_profiles"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT,
        TABLE,
        "users",
        ["confirmed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT,
        TABLE,
        "users",
        ["confirmed_by"],
        ["id"],
    )
