"""make_pipeline_job_id_nullable_in_raw_llm_responses

Revision ID: 5f6bc1cccd0a
Revises: 146fa2cf3221
Create Date: 2026-02-10 15:35:22.334623

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5f6bc1cccd0a'
down_revision: str | Sequence[str] | None = '146fa2cf3221'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # 1. Create new table with nullable pipeline_job_id
    op.execute("""
        CREATE TABLE raw_llm_responses_new (
            id INTEGER NOT NULL PRIMARY KEY,
            content TEXT NOT NULL,
            llm_provider VARCHAR(20) NOT NULL,
            llm_model VARCHAR(100) NOT NULL,
            tokens_used INTEGER,
            latency_ms INTEGER,
            raw_response_json JSON,
            error_message TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            query_id INTEGER NOT NULL,
            pipeline_job_id INTEGER,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            FOREIGN KEY(query_id) REFERENCES expanded_queries (id) ON DELETE CASCADE,
            FOREIGN KEY(pipeline_job_id) REFERENCES pipeline_jobs (id) ON DELETE CASCADE
        )
    """)

    # 2. Copy data
    op.execute("""
        INSERT INTO raw_llm_responses_new
        SELECT * FROM raw_llm_responses
    """)

    # 3. Drop old table
    op.drop_table('raw_llm_responses')

    # 4. Rename new table
    op.execute("""
        ALTER TABLE raw_llm_responses_new RENAME TO raw_llm_responses
    """)

    # 5. Recreate indexes
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


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate with NOT NULL constraint
    op.execute("""
        CREATE TABLE raw_llm_responses_new (
            id INTEGER NOT NULL PRIMARY KEY,
            content TEXT NOT NULL,
            llm_provider VARCHAR(20) NOT NULL,
            llm_model VARCHAR(100) NOT NULL,
            tokens_used INTEGER,
            latency_ms INTEGER,
            raw_response_json JSON,
            error_message TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            query_id INTEGER NOT NULL,
            pipeline_job_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            FOREIGN KEY(query_id) REFERENCES expanded_queries (id) ON DELETE CASCADE,
            FOREIGN KEY(pipeline_job_id) REFERENCES pipeline_jobs (id) ON DELETE CASCADE
        )
    """)

    # Copy data (will fail if any pipeline_job_id is NULL)
    op.execute("""
        INSERT INTO raw_llm_responses_new
        SELECT * FROM raw_llm_responses
    """)

    op.drop_table('raw_llm_responses')

    op.execute("""
        ALTER TABLE raw_llm_responses_new RENAME TO raw_llm_responses
    """)

    # Recreate indexes
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
