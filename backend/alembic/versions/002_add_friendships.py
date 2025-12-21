"""Add friendships table

Revision ID: 002_friendships
Revises: 001_google_calendar
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_friendships'
down_revision = '001_google_calendar'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    # Add telegram_username to users if it doesn't exist
    users_columns = [col['name'] for col in inspector.get_columns('users')]
    if 'telegram_username' not in users_columns:
        op.add_column('users', sa.Column('telegram_username', sa.String(), nullable=True))
        op.create_index('ix_users_telegram_username', 'users', ['telegram_username'])

    # Create friendships table only if it doesn't exist
    if 'friendships' not in inspector.get_table_names():
        op.create_table(
            'friendships',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('from_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('to_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('status', sa.Enum('pending', 'accepted', 'rejected', name='friendshipstatus'), default='pending'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_friendships_from_user_id', 'friendships', ['from_user_id'])
        op.create_index('ix_friendships_to_user_id', 'friendships', ['to_user_id'])


def downgrade() -> None:
    op.drop_index('ix_friendships_to_user_id', 'friendships')
    op.drop_index('ix_friendships_from_user_id', 'friendships')
    op.drop_table('friendships')
    op.drop_index('ix_users_telegram_username', 'users')
    op.drop_column('users', 'telegram_username')
