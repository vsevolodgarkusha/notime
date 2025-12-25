"""Add completed_at field and merge cancelled into completed status

Revision ID: 006_completed_at
Revises: 005_remove_friends
Create Date: 2025-12-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_completed_at'
down_revision = '005_remove_friends'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    # Add completed_at column to tasks table if it doesn't exist
    tasks_columns = [col['name'] for col in inspector.get_columns('tasks')]
    if 'completed_at' not in tasks_columns:
        op.add_column('tasks', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))

    # Populate completed_at for existing completed and cancelled tasks
    # For these tasks, set completed_at = due_date
    op.execute("""
        UPDATE tasks
        SET completed_at = due_date
        WHERE status IN ('completed', 'cancelled') AND completed_at IS NULL
    """)

    # Migrate all 'cancelled' status to 'completed'
    op.execute("""
        UPDATE tasks
        SET status = 'completed'
        WHERE status = 'cancelled'
    """)

    # Remove 'cancelled' from the enum type
    # PostgreSQL doesn't support removing enum values directly, so we need to:
    # 1. Create a new enum type without 'cancelled'
    # 2. Alter the column to use the new type
    # 3. Drop the old type

    # Create new enum type
    op.execute("CREATE TYPE taskstatus_new AS ENUM ('created', 'scheduled', 'sent', 'completed')")

    # Change column to use new type
    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN status TYPE taskstatus_new
        USING status::text::taskstatus_new
    """)

    # Drop old type and rename new one
    op.execute("DROP TYPE taskstatus")
    op.execute("ALTER TYPE taskstatus_new RENAME TO taskstatus")


def downgrade() -> None:
    # Add back the cancelled status to enum
    op.execute("CREATE TYPE taskstatus_new AS ENUM ('created', 'scheduled', 'sent', 'completed', 'cancelled')")
    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN status TYPE taskstatus_new
        USING status::text::taskstatus_new
    """)
    op.execute("DROP TYPE taskstatus")
    op.execute("ALTER TYPE taskstatus_new RENAME TO taskstatus")

    # Note: We cannot restore which tasks were originally cancelled vs completed
    # Drop completed_at column
    op.drop_column('tasks', 'completed_at')
