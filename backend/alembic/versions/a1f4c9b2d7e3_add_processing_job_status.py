"""add processing job status

Revision ID: a1f4c9b2d7e3
Revises: 7c2a87de6f3e
Create Date: 2026-06-14 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1f4c9b2d7e3'
down_revision: Union[str, Sequence[str], None] = '7c2a87de6f3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the 'processing' value to the jobstatus enum.

    PostgreSQL 15 supports ADD VALUE inside a transaction, so no AUTOCOMMIT
    handling is needed here.
    """
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'processing'")


def downgrade() -> None:
    """No-op.

    Removing a value from a PostgreSQL enum requires recreating the type and
    rewriting every dependent column, which is not safe to automate. Leaving
    the extra value in place is harmless.
    """
    pass
