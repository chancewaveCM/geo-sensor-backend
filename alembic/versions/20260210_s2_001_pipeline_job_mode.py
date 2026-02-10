"""Add mode column to pipeline_jobs.

Revision ID: s2_001_mode
Revises: fc7f83892ef1
Create Date: 2026-02-10
"""
from alembic import op
import sqlalchemy as sa

revision = "s2_001_mode"
down_revision = "fc7f83892ef1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_jobs",
        sa.Column("mode", sa.String(20), server_default="pipeline", nullable=False),
    )
    # Backfill existing rows
    op.execute("UPDATE pipeline_jobs SET mode = 'pipeline' WHERE mode IS NULL")


def downgrade() -> None:
    op.drop_column("pipeline_jobs", "mode")
