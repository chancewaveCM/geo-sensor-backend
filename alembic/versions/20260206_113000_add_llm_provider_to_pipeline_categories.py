"""add_llm_provider_to_pipeline_categories

Revision ID: 20260206_113000
Revises: 20260205_154500
Create Date: 2026-02-06 11:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260206_113000"
down_revision: Union[str, Sequence[str], None] = "20260205_154500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "pipeline_categories",
        sa.Column("llm_provider", sa.String(length=20), nullable=False, server_default="gemini"),
    )
    op.create_index(
        op.f("ix_pipeline_categories_llm_provider"),
        "pipeline_categories",
        ["llm_provider"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_pipeline_categories_llm_provider"), table_name="pipeline_categories")
    op.drop_column("pipeline_categories", "llm_provider")
