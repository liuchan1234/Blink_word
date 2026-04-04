#!/bin/sh
set -e
PORT="${PORT:-8000}"
WORKERS="${UVICORN_WORKERS:-4}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers "$WORKERS" --loop uvloop --http httptools
