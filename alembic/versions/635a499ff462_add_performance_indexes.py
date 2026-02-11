"""add_performance_indexes

Revision ID: 635a499ff462
Revises: b09dd2ff507f
Create Date: 2026-02-11 13:15:31.501385

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '635a499ff462'
down_revision: Union[str, Sequence[str], None] = 'b09dd2ff507f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add indexes on pipeline_jobs for common query patterns
    with op.batch_alter_table('pipeline_jobs', schema=None) as batch_op:
        batch_op.create_index('ix_pipeline_jobs_campaign_id', ['campaign_id'])
        batch_op.create_index('ix_pipeline_jobs_workspace_id', ['workspace_id'])
        batch_op.create_index('ix_pipeline_jobs_created_at', ['created_at'])

    # Add indexes on campaign_annotations for time-series queries
    with op.batch_alter_table('campaign_annotations', schema=None) as batch_op:
        batch_op.create_index('ix_campaign_annotations_campaign_id', ['campaign_id'])
        batch_op.create_index('ix_campaign_annotations_created_at', ['created_at'])

    # Add index on generated_queries for join performance
    with op.batch_alter_table('generated_queries', schema=None) as batch_op:
        batch_op.create_index('ix_generated_queries_pipeline_job_id', ['pipeline_job_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes in reverse order
    with op.batch_alter_table('generated_queries', schema=None) as batch_op:
        batch_op.drop_index('ix_generated_queries_pipeline_job_id')

    with op.batch_alter_table('campaign_annotations', schema=None) as batch_op:
        batch_op.drop_index('ix_campaign_annotations_created_at')
        batch_op.drop_index('ix_campaign_annotations_campaign_id')

    with op.batch_alter_table('pipeline_jobs', schema=None) as batch_op:
        batch_op.drop_index('ix_pipeline_jobs_created_at')
        batch_op.drop_index('ix_pipeline_jobs_workspace_id')
        batch_op.drop_index('ix_pipeline_jobs_campaign_id')
