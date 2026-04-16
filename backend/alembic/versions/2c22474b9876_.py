"""empty message

Revision ID: 2c22474b9876
Revises: 9dea052eee65
Create Date: 2026-04-14 02:43:24.624981

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c22474b9876'
down_revision: Union[str, Sequence[str], None] = '9dea052eee65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade():
    op.execute("ALTER TYPE userrole ADD VALUE 'employee'")
    op.add_column(
        "templates",
        sa.Column("renderer_type", sa.String(), nullable=True, server_default="simple")
    )


def downgrade():
    op.drop_column("templates", "renderer_type")
    raise NotImplementedError("Downgrade for enum value removal is not supported")
