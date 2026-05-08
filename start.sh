#!/usr/bin/env bash
# Production başlatma scripti — VPS / Docker ortamı için.
# PaaS (Render, Railway) için Procfile kullanılır.

set -euo pipefail

# Migration uygula
alembic upgrade head

# Müfredat seed (idempotent — yoksa ekler, varsa atlar)
python -m scripts.seed || true

# Gunicorn ile başlat (uvicorn worker'ları)
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"
exec gunicorn app.main:app \
    -w "$WORKERS" \
    -k uvicorn.workers.UvicornWorker \
    -b "0.0.0.0:$PORT" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
