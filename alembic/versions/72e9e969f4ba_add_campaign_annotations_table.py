"""add campaign annotations table

Revision ID: 72e9e969f4ba
Revises: 7bcc1f829057
Create Date: 2026-02-11 12:59:08.595766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72e9e969f4ba'
down_revision: Union[str, Sequence[str], None] = '7bcc1f829057'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('campaign_annotations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('annotation_type', sa.String(length=50), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column(
        'created_at', sa.DateTime(timezone=True),
        server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False,
    ),
    sa.Column(
        'updated_at', sa.DateTime(timezone=True),
        server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False,
    ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('campaign_annotations', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_campaign_annotations_campaign_id'),
            ['campaign_id'], unique=False,
        )
        batch_op.create_index(batch_op.f('ix_campaign_annotations_id'), ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('campaign_annotations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaign_annotations_id'))
        batch_op.drop_index(batch_op.f('ix_campaign_annotations_campaign_id'))

    op.drop_table('campaign_annotations')
