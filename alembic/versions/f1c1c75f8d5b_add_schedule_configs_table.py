"""add schedule_configs table

Revision ID: f1c1c75f8d5b
Revises: 54ca84b559b1
Create Date: 2026-02-09 11:39:51.242802

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1c1c75f8d5b'
down_revision: str | Sequence[str] | None = '54ca84b559b1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'schedule_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interval_minutes', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('llm_providers', sa.JSON(), nullable=False),
        sa.Column(
            'failure_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
        sa.Column('query_set_id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['query_set_id'], ['query_sets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('query_set_id'),
    )
    op.create_index(
        op.f('ix_schedule_configs_id'),
        'schedule_configs',
        ['id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_schedule_configs_id'), table_name='schedule_configs')
    op.drop_table('schedule_configs')
