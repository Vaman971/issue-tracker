#!/bin/sh

set -e

echo "Starting FastAPI production server..."
exec gunicorn app.main:app \
  --workers "${WEB_CONCURRENCY:-1}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --worker-tmp-dir /dev/shm \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --forwarded-allow-ips "*"
