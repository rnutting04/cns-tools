"""add budget layout profiles and job layout review columns

Revision ID: a7d9c3f1b204
Revises: e3a7b5c2f1d9
Create Date: 2026-08-25

Adds the confirmed-layout store that lets one human review cover every
association sharing a workbook template, plus the two columns on budget_jobs
that park a run while its layout is being confirmed.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7d9c3f1b204"
down_revision: Union[str, Sequence[str], None] = "e3a7b5c2f1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budget_layout_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signature", sa.String(length=32), nullable=False),
        sa.Column("sheet_title", sa.String(length=255), nullable=False),
        sa.Column("header_row", sa.Integer(), nullable=False),
        sa.Column("label_col", sa.Integer(), nullable=False),
        sa.Column("prior_col", sa.Integer(), nullable=True),
        sa.Column("projected_col", sa.Integer(), nullable=True),
        sa.Column("proposed_col", sa.Integer(), nullable=True),
        sa.Column("notes_col", sa.Integer(), nullable=True),
        sa.Column("reserve_sheet", sa.String(length=255), nullable=True),
        sa.Column("section_rows", sa.JSON(), nullable=False),
        sa.Column("value_cols", sa.JSON(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("example_association", sa.String(length=255), nullable=True),
        sa.Column("example_filename", sa.String(length=255), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "confirmed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_budget_layout_profiles_signature",
        "budget_layout_profiles",
        ["signature"],
        unique=True,
    )
    op.create_index(
        "ix_budget_layout_profiles_confirmed",
        "budget_layout_profiles",
        ["confirmed"],
    )

    op.add_column("budget_jobs", sa.Column("layout_signature", sa.String(length=32), nullable=True))
    op.add_column("budget_jobs", sa.Column("layout_review", sa.JSON(), nullable=True))
    op.create_index("ix_budget_jobs_layout_signature", "budget_jobs", ["layout_signature"])


def downgrade() -> None:
    op.drop_index("ix_budget_jobs_layout_signature", table_name="budget_jobs")
    op.drop_column("budget_jobs", "layout_review")
    op.drop_column("budget_jobs", "layout_signature")
    op.drop_index("ix_budget_layout_profiles_confirmed", table_name="budget_layout_profiles")
    op.drop_index("ix_budget_layout_profiles_signature", table_name="budget_layout_profiles")
    op.drop_table("budget_layout_profiles")
