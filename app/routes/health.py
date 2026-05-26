"""Sağlık kontrolü endpoint'i — uptime monitör ve PaaS health check için."""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine


router = APIRouter()


# UptimeRobot ve benzeri monitör araçları varsayılan olarak HEAD kullanır
# (daha hafif). Sadece GET tanımlanırsa 405 dönüp monitor "Down" gösterir.
# Hem GET hem HEAD kabul ederek dışsal monitorlerin doğru çalışmasını sağlıyoruz.
@router.api_route("/healthz", methods=["GET", "HEAD"])
def healthz() -> dict:
    """Uygulama + DB bağlantısı sağlıklı mı?"""
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "up" if db_ok else "down",
        "time": datetime.now(timezone.utc).isoformat(),
    }
