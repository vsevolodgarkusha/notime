"""Add timezone to timestamps

Revision ID: 004_timezone_support
Revises: 003_scheduled_status
Create Date: 2025-12-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_timezone_support'
down_revision = '003_scheduled_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('tasks', 'due_date',
               existing_type=sa.DATETIME(),
               type_=sa.DateTime(timezone=True),
               nullable=True,
               postgresql_using='due_date AT TIME ZONE \'UTC\'')
    op.alter_column('tasks', 'created_at',
               existing_type=sa.DATETIME(),
               type_=sa.DateTime(timezone=True),
               nullable=True,
               postgresql_using='created_at AT TIME ZONE \'UTC\'')


def downgrade() -> None:
    op.alter_column('tasks', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.DATETIME(),
               nullable=True)
    op.alter_column('tasks', 'due_date',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.DATETIME(),
               nullable=True)