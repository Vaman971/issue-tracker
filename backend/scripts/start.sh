#!/bin/sh

set -e

echo "Starting FastAPI production server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers