#!/bin/sh

set -e

echo "Starting FastAPI production server..."
exec gunicorn app.main:app \
  --workers "${WEB_CONCURRENCY:-1}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --worker-tmp-dir /dev/shm \
  --timeout 120 \
  --keepalive 5 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --proxy-headers \
  --forwarded-allow-ips "*"
