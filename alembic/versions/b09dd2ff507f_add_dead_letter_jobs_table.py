"""add dead letter jobs table

Revision ID: b09dd2ff507f
Revises: 72e9e969f4ba
Create Date: 2026-02-11 13:05:37.224319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b09dd2ff507f'
down_revision: Union[str, Sequence[str], None] = '72e9e969f4ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add dead_letter_jobs table."""
    op.create_table('dead_letter_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
    sa.Column('failed_at', sa.DateTime(), nullable=False),
    sa.Column('last_retry_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='failed', nullable=False),
    sa.Column(
        'created_at', sa.DateTime(timezone=True),
        server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False
    ),
    sa.Column(
        'updated_at', sa.DateTime(timezone=True),
        server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False
    ),
    sa.ForeignKeyConstraint(['job_id'], ['pipeline_jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('dead_letter_jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dead_letter_jobs_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_dead_letter_jobs_job_id'), ['job_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - remove dead_letter_jobs table."""
    with op.batch_alter_table('dead_letter_jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dead_letter_jobs_job_id'))
        batch_op.drop_index(batch_op.f('ix_dead_letter_jobs_id'))

    op.drop_table('dead_letter_jobs')
