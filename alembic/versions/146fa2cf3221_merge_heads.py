"""merge_heads

Revision ID: 146fa2cf3221
Revises: s2_001_mode, fbf740290fe7
Create Date: 2026-02-10 15:35:10.635363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '146fa2cf3221'
down_revision: Union[str, Sequence[str], None] = ('s2_001_mode', 'fbf740290fe7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
