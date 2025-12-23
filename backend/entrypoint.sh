#!/bin/bash
set -e

echo "Waiting for database..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "Database is ready!"

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting application..."
exec "$@"
