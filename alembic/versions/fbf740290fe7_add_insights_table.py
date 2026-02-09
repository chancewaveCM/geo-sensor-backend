"""add insights table

Revision ID: fbf740290fe7
Revises: 728517b00d87
Create Date: 2026-02-09 16:37:37.892860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbf740290fe7'
down_revision: Union[str, Sequence[str], None] = '728517b00d87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('insights',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workspace_id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('insight_type', sa.String(length=50), nullable=False),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('data_json', sa.Text(), nullable=True),
    sa.Column('is_dismissed', sa.Boolean(), nullable=False),
    sa.Column(
        'created_at',
        sa.DateTime(timezone=True),
        server_default=sa.text('(CURRENT_TIMESTAMP)'),
        nullable=False,
    ),
    sa.Column(
        'updated_at',
        sa.DateTime(timezone=True),
        server_default=sa.text('(CURRENT_TIMESTAMP)'),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_insights_campaign_id'), 'insights', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_insights_id'), 'insights', ['id'], unique=False)
    op.create_index(op.f('ix_insights_workspace_id'), 'insights', ['workspace_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_insights_workspace_id'), table_name='insights')
    op.drop_index(op.f('ix_insights_id'), table_name='insights')
    op.drop_index(op.f('ix_insights_campaign_id'), table_name='insights')
    op.drop_table('insights')
