"""add workspace and workspace_member tables

Revision ID: 20260206_170600
Revises: 20260206_113000
Create Date: 2026-02-06 17:06:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260206_170600'
down_revision: Union[str, Sequence[str], None] = '20260206_113000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create workspace tables."""
    # Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_workspaces_id'), 'workspaces', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_workspaces_slug'), 'workspaces', ['slug'], unique=True
    )

    # Create workspace_members table
    op.create_table(
        'workspace_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('invited_by', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False
        ),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['workspace_id'], ['workspaces.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user')
    )
    op.create_index(
        op.f('ix_workspace_members_id'), 'workspace_members', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_workspace_members_user_id'),
        'workspace_members',
        ['user_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_workspace_members_workspace_id'),
        'workspace_members',
        ['workspace_id'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema - drop workspace tables."""
    op.drop_index(
        op.f('ix_workspace_members_workspace_id'), table_name='workspace_members'
    )
    op.drop_index(
        op.f('ix_workspace_members_user_id'), table_name='workspace_members'
    )
    op.drop_index(
        op.f('ix_workspace_members_id'), table_name='workspace_members'
    )
    op.drop_table('workspace_members')
    op.drop_index(op.f('ix_workspaces_slug'), table_name='workspaces')
    op.drop_index(op.f('ix_workspaces_id'), table_name='workspaces')
    op.drop_table('workspaces')
