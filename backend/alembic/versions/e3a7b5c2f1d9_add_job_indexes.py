"""add indexes on job FK columns

Revision ID: e3a7b5c2f1d9
Revises: d4f8c1b2e9a7
Create Date: 2026-07-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e3a7b5c2f1d9'
down_revision: Union[str, Sequence[str], None] = 'd4f8c1b2e9a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_letter_jobs_created_by', 'letter_jobs', ['created_by'])
    op.create_index('ix_letter_jobs_association_id', 'letter_jobs', ['association_id'])
    op.create_index('ix_letter_jobs_template_id', 'letter_jobs', ['template_id'])
    op.create_index('ix_budget_jobs_created_by', 'budget_jobs', ['created_by'])


def downgrade() -> None:
    op.drop_index('ix_budget_jobs_created_by', table_name='budget_jobs')
    op.drop_index('ix_letter_jobs_template_id', table_name='letter_jobs')
    op.drop_index('ix_letter_jobs_association_id', table_name='letter_jobs')
    op.drop_index('ix_letter_jobs_created_by', table_name='letter_jobs')
