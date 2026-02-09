"""add_performance_indexes

Revision ID: 728517b00d87
Revises: f1c1c75f8d5b
Create Date: 2026-02-09 16:23:48.638493

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '728517b00d87'
down_revision: str | Sequence[str] | None = 'f1c1c75f8d5b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add performance indexes (only missing ones)."""
    # schedule_configs
    op.create_index(
        'ix_schedule_configs_is_active',
        'schedule_configs',
        ['is_active']
    )
    op.create_index(
        'ix_schedule_configs_next_run_at',
        'schedule_configs',
        ['next_run_at']
    )

    # pipeline_jobs
    op.create_index(
        'ix_pipeline_jobs_created_at',
        'pipeline_jobs',
        ['created_at']
    )

    # pipeline_categories
    op.create_index(
        'ix_pipeline_categories_persona_type',
        'pipeline_categories',
        ['persona_type']
    )

    # raw_llm_responses
    op.create_index(
        'ix_raw_llm_responses_created_at',
        'raw_llm_responses',
        ['created_at']
    )

    # campaigns
    op.create_index('ix_campaigns_status', 'campaigns', ['status'])
    op.create_index(
        'ix_campaigns_schedule_enabled',
        'campaigns',
        ['schedule_enabled']
    )
    op.create_index(
        'ix_campaigns_schedule_next_run_at',
        'campaigns',
        ['schedule_next_run_at']
    )

    # intent_clusters
    op.create_index(
        'ix_intent_clusters_order_index',
        'intent_clusters',
        ['order_index']
    )

    # query_definitions
    op.create_index(
        'ix_query_definitions_created_by',
        'query_definitions',
        ['created_by']
    )
    op.create_index(
        'ix_query_definitions_is_active',
        'query_definitions',
        ['is_active']
    )
    op.create_index(
        'ix_query_definitions_query_type',
        'query_definitions',
        ['query_type']
    )

    # query_versions
    op.create_index(
        'ix_query_versions_changed_by',
        'query_versions',
        ['changed_by']
    )
    op.create_index(
        'ix_query_versions_is_current',
        'query_versions',
        ['is_current']
    )
    op.create_index(
        'ix_query_versions_effective_from',
        'query_versions',
        ['effective_from']
    )

    # prompt_templates
    op.create_index(
        'ix_prompt_templates_changed_by',
        'prompt_templates',
        ['changed_by']
    )
    op.create_index(
        'ix_prompt_templates_is_current',
        'prompt_templates',
        ['is_current']
    )

    # campaign_runs
    op.create_index(
        'ix_campaign_runs_status',
        'campaign_runs',
        ['status']
    )
    op.create_index(
        'ix_campaign_runs_prompt_version_id',
        'campaign_runs',
        ['prompt_version_id']
    )
    op.create_index(
        'ix_campaign_runs_trigger_type',
        'campaign_runs',
        ['trigger_type']
    )
    op.create_index(
        'ix_campaign_runs_started_at',
        'campaign_runs',
        ['started_at']
    )

    # run_responses
    op.create_index(
        'ix_run_responses_llm_provider',
        'run_responses',
        ['llm_provider']
    )
    op.create_index(
        'ix_run_responses_response_hash',
        'run_responses',
        ['response_hash']
    )
    op.create_index(
        'ix_run_responses_created_at',
        'run_responses',
        ['created_at']
    )

    # campaign_companies
    op.create_index(
        'ix_campaign_companies_added_by',
        'campaign_companies',
        ['added_by']
    )
    op.create_index(
        'ix_campaign_companies_is_target_brand',
        'campaign_companies',
        ['is_target_brand']
    )

    # run_citations
    op.create_index(
        'ix_run_citations_cited_brand',
        'run_citations',
        ['cited_brand']
    )
    op.create_index(
        'ix_run_citations_is_target_brand',
        'run_citations',
        ['is_target_brand']
    )
    op.create_index(
        'ix_run_citations_verified_by',
        'run_citations',
        ['verified_by']
    )

    # response_labels
    op.create_index(
        'ix_response_labels_label_type',
        'response_labels',
        ['label_type']
    )
    op.create_index(
        'ix_response_labels_created_by',
        'response_labels',
        ['created_by']
    )
    op.create_index(
        'ix_response_labels_resolved_by',
        'response_labels',
        ['resolved_by']
    )

    # citation_reviews
    op.create_index(
        'ix_citation_reviews_review_type',
        'citation_reviews',
        ['review_type']
    )
    op.create_index(
        'ix_citation_reviews_created_by',
        'citation_reviews',
        ['created_by']
    )

    # comparison_snapshots
    op.create_index(
        'ix_comparison_snapshots_comparison_type',
        'comparison_snapshots',
        ['comparison_type']
    )
    op.create_index(
        'ix_comparison_snapshots_created_by',
        'comparison_snapshots',
        ['created_by']
    )

    # operation_logs
    op.create_index(
        'ix_operation_logs_operation_type',
        'operation_logs',
        ['operation_type']
    )
    op.create_index(
        'ix_operation_logs_status',
        'operation_logs',
        ['status']
    )
    op.create_index(
        'ix_operation_logs_created_by',
        'operation_logs',
        ['created_by']
    )
    op.create_index(
        'ix_operation_logs_reviewed_by',
        'operation_logs',
        ['reviewed_by']
    )

    # Composite indexes for common query patterns
    op.create_index(
        'ix_pipeline_jobs_status_created',
        'pipeline_jobs',
        ['status', 'created_at']
    )
    op.create_index(
        'ix_campaign_runs_campaign_status',
        'campaign_runs',
        ['campaign_id', 'status']
    )
    op.create_index(
        'ix_run_responses_run_provider',
        'run_responses',
        ['campaign_run_id', 'llm_provider']
    )
    op.create_index(
        'ix_expanded_queries_category_status',
        'expanded_queries',
        ['category_id', 'status']
    )


def downgrade() -> None:
    """Remove performance indexes."""
    # Composite indexes
    op.drop_index('ix_expanded_queries_category_status')
    op.drop_index('ix_run_responses_run_provider')
    op.drop_index('ix_campaign_runs_campaign_status')
    op.drop_index('ix_pipeline_jobs_status_created')

    # operation_logs
    op.drop_index('ix_operation_logs_reviewed_by')
    op.drop_index('ix_operation_logs_created_by')
    op.drop_index('ix_operation_logs_status')
    op.drop_index('ix_operation_logs_operation_type')

    # comparison_snapshots
    op.drop_index('ix_comparison_snapshots_created_by')
    op.drop_index('ix_comparison_snapshots_comparison_type')

    # citation_reviews
    op.drop_index('ix_citation_reviews_created_by')
    op.drop_index('ix_citation_reviews_review_type')

    # response_labels
    op.drop_index('ix_response_labels_resolved_by')
    op.drop_index('ix_response_labels_created_by')
    op.drop_index('ix_response_labels_label_type')

    # run_citations
    op.drop_index('ix_run_citations_verified_by')
    op.drop_index('ix_run_citations_is_target_brand')
    op.drop_index('ix_run_citations_cited_brand')

    # campaign_companies
    op.drop_index('ix_campaign_companies_is_target_brand')
    op.drop_index('ix_campaign_companies_added_by')

    # run_responses
    op.drop_index('ix_run_responses_created_at')
    op.drop_index('ix_run_responses_response_hash')
    op.drop_index('ix_run_responses_llm_provider')

    # campaign_runs
    op.drop_index('ix_campaign_runs_started_at')
    op.drop_index('ix_campaign_runs_trigger_type')
    op.drop_index('ix_campaign_runs_prompt_version_id')
    op.drop_index('ix_campaign_runs_status')

    # prompt_templates
    op.drop_index('ix_prompt_templates_is_current')
    op.drop_index('ix_prompt_templates_changed_by')

    # query_versions
    op.drop_index('ix_query_versions_effective_from')
    op.drop_index('ix_query_versions_is_current')
    op.drop_index('ix_query_versions_changed_by')

    # query_definitions
    op.drop_index('ix_query_definitions_query_type')
    op.drop_index('ix_query_definitions_is_active')
    op.drop_index('ix_query_definitions_created_by')

    # intent_clusters
    op.drop_index('ix_intent_clusters_order_index')

    # campaigns
    op.drop_index('ix_campaigns_schedule_next_run_at')
    op.drop_index('ix_campaigns_schedule_enabled')
    op.drop_index('ix_campaigns_status')

    # raw_llm_responses
    op.drop_index('ix_raw_llm_responses_created_at')

    # pipeline_categories
    op.drop_index('ix_pipeline_categories_persona_type')

    # pipeline_jobs
    op.drop_index('ix_pipeline_jobs_created_at')

    # schedule_configs
    op.drop_index('ix_schedule_configs_next_run_at')
    op.drop_index('ix_schedule_configs_is_active')
