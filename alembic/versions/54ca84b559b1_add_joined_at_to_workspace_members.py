"""add joined_at to workspace_members

Revision ID: 54ca84b559b1
Revises: fc7f83892ef1
Create Date: 2026-02-06 17:43:30.662016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '54ca84b559b1'
down_revision: Union[str, Sequence[str], None] = 'fc7f83892ef1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add joined_at column to workspace_members."""
    op.add_column(
        'workspace_members',
        sa.Column(
            'joined_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove joined_at column from workspace_members."""
    op.drop_column('workspace_members', 'joined_at')
