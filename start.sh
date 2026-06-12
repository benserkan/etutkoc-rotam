#!/usr/bin/env bash
# Production başlatma scripti — VPS / Docker ortamı için.
# PaaS (Render, Railway) için Procfile kullanılır.

set -euo pipefail

# DB başlat — boş DB'de modellerden create_all+stamp, mevcut DB'de upgrade head.
# (Initial migration tabloları alfabetik yaratıyor → boş Postgres'te FK ordering
# çöküyor; init_db doğru sırada kurar. Detay: scripts/init_db.py)
python -m scripts.init_db

# Müfredat seed (idempotent — yoksa ekler, varsa atlar)
python -m scripts.seed || true

# Anasayfa vitrin kartları seed (idempotent — var olanı ezmez, admin düzenlemeleri korunur)
python -m scripts.seed_landing_cards || true

# WhatsApp şablonları seed (35 şablon, idempotent — key varsa atlar, düzenlemeleri korur).
# Prod'da unutulmuştu → /admin/whatsapp-templates boş geliyordu (2026-06-01).
python -m scripts.seed_whatsapp_templates || true

# Anket kataloğu seed (11 tanıma anketi, idempotent — code varsa atlar, düzenlemeleri korur)
python -m scripts.seed_surveys || true

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
