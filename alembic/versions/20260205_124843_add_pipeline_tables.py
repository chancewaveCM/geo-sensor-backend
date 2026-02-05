"""add_pipeline_tables

Revision ID: 20260205_124843
Revises: bb919bd56568
Create Date: 2026-02-05 12:48:43

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260205_124843'
down_revision: str | Sequence[str] | None = 'bb919bd56568'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Note: SQLite doesn't support ENUMs, so we use String with constraints
    # When migrating to PostgreSQL, these should be converted to proper ENUMs

    # Create query_sets table
    op.create_table(
        'query_sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category_count', sa.Integer(), nullable=False),
        sa.Column('queries_per_category', sa.Integer(), nullable=False),
        sa.Column('company_profile_id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ['company_profile_id'],
            ['company_profiles.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['owner_id'], ['users.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_query_sets_id'), 'query_sets', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_query_sets_company_profile_id'),
        'query_sets',
        ['company_profile_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_query_sets_owner_id'),
        'query_sets',
        ['owner_id'],
        unique=False
    )

    # Create pipeline_jobs table
    op.create_table(
        'pipeline_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('llm_providers', sa.JSON(), nullable=False),
        sa.Column(
            'total_queries',
            sa.Integer(),
            nullable=False,
            server_default='0'
        ),
        sa.Column(
            'completed_queries',
            sa.Integer(),
            nullable=False,
            server_default='0'
        ),
        sa.Column(
            'failed_queries',
            sa.Integer(),
            nullable=False,
            server_default='0'
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'completed_at', sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('query_set_id', sa.Integer(), nullable=False),
        sa.Column('company_profile_id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ['query_set_id'], ['query_sets.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['company_profile_id'],
            ['company_profiles.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['owner_id'], ['users.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_pipeline_jobs_id'),
        'pipeline_jobs',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_pipeline_jobs_query_set_id'),
        'pipeline_jobs',
        ['query_set_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_pipeline_jobs_company_profile_id'),
        'pipeline_jobs',
        ['company_profile_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_pipeline_jobs_owner_id'),
        'pipeline_jobs',
        ['owner_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_pipeline_jobs_status'),
        'pipeline_jobs',
        ['status'],
        unique=False
    )

    # Create pipeline_categories table
    op.create_table(
        'pipeline_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('persona_type', sa.String(20), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('query_set_id', sa.Integer(), nullable=False),
        sa.Column('company_profile_id', sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ['query_set_id'], ['query_sets.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['company_profile_id'],
            ['company_profiles.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_pipeline_categories_id'),
        'pipeline_categories',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_pipeline_categories_query_set_id'),
        'pipeline_categories',
        ['query_set_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_pipeline_categories_company_profile_id'),
        'pipeline_categories',
        ['company_profile_id'],
        unique=False
    )

    # Create expanded_queries table
    op.create_table(
        'expanded_queries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ['category_id'],
            ['pipeline_categories.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_expanded_queries_id'),
        'expanded_queries',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_expanded_queries_category_id'),
        'expanded_queries',
        ['category_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_expanded_queries_status'),
        'expanded_queries',
        ['status'],
        unique=False
    )

    # Create raw_llm_responses table
    op.create_table(
        'raw_llm_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('llm_provider', sa.String(20), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('raw_response_json', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column(
            'retry_count',
            sa.Integer(),
            nullable=False,
            server_default='0'
        ),
        sa.Column('query_id', sa.Integer(), nullable=False),
        sa.Column('pipeline_job_id', sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ['query_id'], ['expanded_queries.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['pipeline_job_id'], ['pipeline_jobs.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_raw_llm_responses_id'),
        'raw_llm_responses',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_raw_llm_responses_query_id'),
        'raw_llm_responses',
        ['query_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_raw_llm_responses_pipeline_job_id'),
        'raw_llm_responses',
        ['pipeline_job_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_raw_llm_responses_llm_provider'),
        'raw_llm_responses',
        ['llm_provider'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order (respect FK dependencies)
    op.drop_index(
        op.f('ix_raw_llm_responses_llm_provider'),
        table_name='raw_llm_responses'
    )
    op.drop_index(
        op.f('ix_raw_llm_responses_pipeline_job_id'),
        table_name='raw_llm_responses'
    )
    op.drop_index(
        op.f('ix_raw_llm_responses_query_id'),
        table_name='raw_llm_responses'
    )
    op.drop_index(
        op.f('ix_raw_llm_responses_id'),
        table_name='raw_llm_responses'
    )
    op.drop_table('raw_llm_responses')

    op.drop_index(
        op.f('ix_expanded_queries_status'),
        table_name='expanded_queries'
    )
    op.drop_index(
        op.f('ix_expanded_queries_category_id'),
        table_name='expanded_queries'
    )
    op.drop_index(
        op.f('ix_expanded_queries_id'),
        table_name='expanded_queries'
    )
    op.drop_table('expanded_queries')

    op.drop_index(
        op.f('ix_pipeline_categories_company_profile_id'),
        table_name='pipeline_categories'
    )
    op.drop_index(
        op.f('ix_pipeline_categories_query_set_id'),
        table_name='pipeline_categories'
    )
    op.drop_index(
        op.f('ix_pipeline_categories_id'),
        table_name='pipeline_categories'
    )
    op.drop_table('pipeline_categories')

    op.drop_index(
        op.f('ix_pipeline_jobs_status'),
        table_name='pipeline_jobs'
    )
    op.drop_index(
        op.f('ix_pipeline_jobs_owner_id'),
        table_name='pipeline_jobs'
    )
    op.drop_index(
        op.f('ix_pipeline_jobs_company_profile_id'),
        table_name='pipeline_jobs'
    )
    op.drop_index(
        op.f('ix_pipeline_jobs_query_set_id'),
        table_name='pipeline_jobs'
    )
    op.drop_index(
        op.f('ix_pipeline_jobs_id'),
        table_name='pipeline_jobs'
    )
    op.drop_table('pipeline_jobs')

    op.drop_index(
        op.f('ix_query_sets_owner_id'),
        table_name='query_sets'
    )
    op.drop_index(
        op.f('ix_query_sets_company_profile_id'),
        table_name='query_sets'
    )
    op.drop_index(
        op.f('ix_query_sets_id'),
        table_name='query_sets'
    )
    op.drop_table('query_sets')
    # Note: No enum types to drop for SQLite
