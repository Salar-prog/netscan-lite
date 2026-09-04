#!/bin/sh
set -e

echo "ns-lite: running database migrations..."
ns-lite db upgrade || echo "ns-lite: db upgrade skipped (no migrations or already up-to-date)"

exec ns-lite serve --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WORKERS:-1}" --log-level "${LOG_LEVEL:-info}"
