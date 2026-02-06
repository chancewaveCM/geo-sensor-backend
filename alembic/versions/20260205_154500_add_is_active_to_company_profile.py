"""add_is_active_to_company_profile

Revision ID: 20260205_154500
Revises: 20260205_124843
Create Date: 2026-02-05 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260205_154500'
down_revision: Union[str, Sequence[str], None] = '20260205_124843'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_active column with default value True
    op.add_column(
        'company_profiles',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('company_profiles', 'is_active')
