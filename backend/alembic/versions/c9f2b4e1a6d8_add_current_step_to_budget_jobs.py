"""add current_step to budget_jobs

Revision ID: c9f2b4e1a6d8
Revises: a1f4c9b2d7e3
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9f2b4e1a6d8'
down_revision: Union[str, Sequence[str], None] = 'b8f3e21d4a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'budget_jobs',
        sa.Column('current_step', sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('budget_jobs', 'current_step')
