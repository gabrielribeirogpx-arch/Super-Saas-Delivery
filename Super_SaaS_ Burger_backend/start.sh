#!/bin/sh
set -e

echo "Running database migrations..."
if command -v alembic >/dev/null 2>&1; then
  alembic upgrade head
else
  python3 - <<'PY'
from alembic.config import main

main(argv=["-c", "alembic.ini", "upgrade", "head"])
PY
fi

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
