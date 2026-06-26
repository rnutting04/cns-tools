"""add budget_jobs table

Revision ID: b8f3e21d4a91
Revises: a1f4c9b2d7e3
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b8f3e21d4a91'
down_revision: Union[str, Sequence[str], None] = 'a1f4c9b2d7e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'budget_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('association_name', sa.String(length=255), nullable=False),
        sa.Column('budget_year', sa.Integer(), nullable=False),
        sa.Column('financial_report_path', sa.String(length=500), nullable=False),
        sa.Column('financial_report_filename', sa.String(length=255), nullable=False),
        sa.Column('prior_budget_path', sa.String(length=500), nullable=False),
        sa.Column('prior_budget_filename', sa.String(length=255), nullable=False),
        sa.Column('output_path', sa.String(length=500), nullable=True),
        sa.Column('review_flag_count', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_detail', sa.JSON(), nullable=True),
        # Reuse the existing jobstatus enum. postgresql.ENUM with create_type=False
        # prevents CREATE TYPE (sa.Enum ignores that flag inside op.create_table).
        sa.Column(
            'status',
            postgresql.ENUM('pending', 'processing', 'complete', 'failed', name='jobstatus', create_type=False),
            nullable=False,
        ),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('budget_jobs')
