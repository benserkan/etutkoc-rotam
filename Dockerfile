# LGS Takip — Production image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Sistem bağımlılıkları (psycopg2 derlemesi için gerekli olabilir; psycopg2-binary kullandığımız için minimum)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları yükle (cache'lenebilir katman)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/
COPY start.sh ./
RUN chmod +x start.sh

# Health check (PaaS için)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/healthz" || exit 1

EXPOSE 8000

CMD ["./start.sh"]
