#!/bin/sh

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding admin user..."
python -m app.db.seed