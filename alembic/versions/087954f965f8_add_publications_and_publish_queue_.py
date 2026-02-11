"""Add publications and publish_queue tables

Revision ID: 087954f965f8
Revises: 635a499ff462
Create Date: 2026-02-11 14:33:07.703900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '087954f965f8'
down_revision: Union[str, Sequence[str], None] = '635a499ff462'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create publications table
    op.create_table(
        'publications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_publications_id'), 'publications', ['id'], unique=False)
    op.create_index(
        op.f('ix_publications_workspace_id'), 'publications', ['workspace_id'], unique=False
    )
    op.create_index(op.f('ix_publications_platform'), 'publications', ['platform'], unique=False)
    op.create_index(op.f('ix_publications_status'), 'publications', ['status'], unique=False)
    op.create_index(
        op.f('ix_publications_scheduled_at'), 'publications', ['scheduled_at'], unique=False
    )

    # Create publish_queue table
    op.create_table(
        'publish_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('publication_id', sa.Integer(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['publication_id'], ['publications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_publish_queue_id'), 'publish_queue', ['id'], unique=False)
    op.create_index(
        op.f('ix_publish_queue_publication_id'), 'publish_queue', ['publication_id'], unique=False
    )
    op.create_index(
        op.f('ix_publish_queue_next_retry_at'), 'publish_queue', ['next_retry_at'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop publish_queue table first (has FK to publications)
    op.drop_index(op.f('ix_publish_queue_next_retry_at'), table_name='publish_queue')
    op.drop_index(op.f('ix_publish_queue_publication_id'), table_name='publish_queue')
    op.drop_index(op.f('ix_publish_queue_id'), table_name='publish_queue')
    op.drop_table('publish_queue')

    # Drop publications table
    op.drop_index(op.f('ix_publications_scheduled_at'), table_name='publications')
    op.drop_index(op.f('ix_publications_status'), table_name='publications')
    op.drop_index(op.f('ix_publications_platform'), table_name='publications')
    op.drop_index(op.f('ix_publications_workspace_id'), table_name='publications')
    op.drop_index(op.f('ix_publications_id'), table_name='publications')
    op.drop_table('publications')
