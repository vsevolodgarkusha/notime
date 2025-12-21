"""Initial schema

Revision ID: 000_initial
Revises:
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '000_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    # Create users table only if it doesn't exist
    if 'users' not in inspector.get_table_names():
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('telegram_id', sa.BigInteger(), unique=True, index=True),
            sa.Column('timezone', sa.String(), nullable=True),
        )

    # Create tasks table only if it doesn't exist
    if 'tasks' not in inspector.get_table_names():
        op.create_table(
            'tasks',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('due_date', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.Enum('created', 'sent', 'completed', 'cancelled', name='taskstatus'), nullable=True),
            sa.Column('message_id', sa.BigInteger(), nullable=True),
            sa.Column('chat_id', sa.BigInteger(), nullable=True),
        )
        op.create_index('ix_tasks_user_id', 'tasks', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_tasks_user_id', 'tasks')
    op.drop_table('tasks')
    op.drop_table('users')
