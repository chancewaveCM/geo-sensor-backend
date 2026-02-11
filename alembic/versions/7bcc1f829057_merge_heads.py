"""merge heads

Revision ID: 7bcc1f829057
Revises: 5f6bc1cccd0a, s1_001_user_settings
Create Date: 2026-02-11 12:58:46.033022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bcc1f829057'
down_revision: Union[str, Sequence[str], None] = ('5f6bc1cccd0a', 's1_001_user_settings')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
