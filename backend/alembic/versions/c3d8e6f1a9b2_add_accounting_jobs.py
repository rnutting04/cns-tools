"""add accounting_jobs table

Background runs of the accounting tools (FDIC exposure, audit threshold)
over combined multi-association PDFs.

Revision ID: c3d8e6f1a9b2
Revises: b5e8d2c47f16
Create Date: 2026-11-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d8e6f1a9b2"
down_revision: Union[str, Sequence[str], None] = "b5e8d2c47f16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounting_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tool", sa.String(length=30), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("input_path", sa.String(length=500), nullable=True),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column("pages_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_association", sa.String(length=255), nullable=True),
        sa.Column("results", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        # Reuse the existing jobstatus enum (see add_budget_jobs).
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "processing", "complete", "failed", name="jobstatus", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounting_jobs_created_by", "accounting_jobs", ["created_by"])
    op.create_index("ix_accounting_jobs_created_at", "accounting_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_accounting_jobs_created_at", table_name="accounting_jobs")
    op.drop_index("ix_accounting_jobs_created_by", table_name="accounting_jobs")
    op.drop_table("accounting_jobs")
