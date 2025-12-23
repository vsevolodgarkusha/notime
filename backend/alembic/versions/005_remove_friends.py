"""Remove friends feature (drop friendships + telegram_username)

Revision ID: 005_remove_friends
Revises: 004_timezone_support
Create Date: 2025-12-23
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "005_remove_friends"
down_revision = "004_timezone_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    # Drop friendships table (and its indexes / FKs) if it exists
    if "friendships" in inspector.get_table_names():
        op.drop_table("friendships")

    # Drop telegram_username column + index if present
    if "users" in inspector.get_table_names():
        users_columns = [col["name"] for col in inspector.get_columns("users")]

        if "telegram_username" in users_columns:
            existing_indexes = {ix["name"] for ix in inspector.get_indexes("users")}
            if "ix_users_telegram_username" in existing_indexes:
                op.drop_index("ix_users_telegram_username", table_name="users")

            op.drop_column("users", "telegram_username")

    # Drop enum type created for friendships (PostgreSQL)
    op.execute("DROP TYPE IF EXISTS friendshipstatus")


def downgrade() -> None:
    # Intentionally not implemented (friends feature removed)
    pass
