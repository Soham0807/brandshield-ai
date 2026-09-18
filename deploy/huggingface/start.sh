#!/usr/bin/env bash
# Use the persistent disk when the Space has one, otherwise fall back to /tmp
# (data then resets when the Space restarts, which is fine for a demo).
set -e
if [ -w /data ]; then
  export DATABASE_PATH=/data/brandshield.db
  export EVALUATION_PATH=/data/evaluation.json
  echo "Using persistent storage at /data (model cache stays in the image)"
else
  export DATABASE_PATH=/tmp/data/brandshield.db
  export EVALUATION_PATH=/tmp/data/evaluation.json
  echo "No persistent disk — data lives in /tmp and resets on restart"
fi
mkdir -p "$(dirname "$DATABASE_PATH")"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
