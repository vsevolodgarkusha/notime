"""Add scheduled status to taskstatus enum

Revision ID: 003_scheduled_status
Revises: 002_friendships
Create Date: 2025-12-22
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '003_scheduled_status'
down_revision = '002_friendships'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'scheduled' AFTER 'created'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values easily
    # This would require recreating the type and all columns using it
    pass
