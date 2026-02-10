"""Add avatar_url and notification_preferences to users table.

Revision ID: s1_001_user_settings
Revises: fc7f83892ef1
Create Date: 2026-02-10
"""
import sqlalchemy as sa

from alembic import op

revision = "s1_001_user_settings"
down_revision = "fc7f83892ef1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("notification_preferences", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "notification_preferences")
    op.drop_column("users", "avatar_url")
