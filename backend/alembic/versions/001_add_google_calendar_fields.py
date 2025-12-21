"""Add Google Calendar fields

Revision ID: 001_google_calendar
Revises: 000_initial
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_google_calendar'
down_revision = '000_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    # Add google_calendar_token to users table if it doesn't exist
    users_columns = [col['name'] for col in inspector.get_columns('users')]
    if 'google_calendar_token' not in users_columns:
        op.add_column('users', sa.Column('google_calendar_token', sa.Text(), nullable=True))

    # Add google_calendar_event_id to tasks table if it doesn't exist
    tasks_columns = [col['name'] for col in inspector.get_columns('tasks')]
    if 'google_calendar_event_id' not in tasks_columns:
        op.add_column('tasks', sa.Column('google_calendar_event_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'google_calendar_event_id')
    op.drop_column('users', 'google_calendar_token')
