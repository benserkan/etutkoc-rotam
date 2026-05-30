"""P6 — WhatsApp spam guard hesaplaması.

Koç için günlük / haftalık dispatch sayımı + uyarı seviyesi. **Engelleme YOK**
— Faz 1 manuel Click-to-WA akışı koçun kendi telefonundan gider, sorumlu koç;
sistem yalnız bilgilendirir. Eşikler keskin değil — koç durdurmak istemezse
devam edebilir, ama "veliler engelleyebilir" uyarısı gösterilir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import User, WhatsAppDispatchLog


# Eşikler
WARN_DAILY_BUSY = 50         # ≥50: amber "yoğun"
WARN_DAILY_HEAVY = 100       # ≥100: rose "çok yoğun"


@dataclass
class DispatchStats:
    today_count: int
    week_count: int
    week_start_iso: str
    warning_level: str        # "ok" | "yogun" | "cok_yogun"
    warning_message: str | None


def _utc_today_start(now: datetime) -> datetime:
    """now'un UTC günün başlangıcı (00:00:00)."""
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _utc_week_start(now: datetime) -> datetime:
    """Pazartesi 00:00 UTC (ISO hafta tanımı)."""
    today = _utc_today_start(now)
    # weekday(): 0=Pazartesi
    return today - timedelta(days=today.weekday())


def _warning_for(today_count: int) -> tuple[str, str | None]:
    if today_count >= WARN_DAILY_HEAVY:
        return (
            "cok_yogun",
            f"Bugün {today_count} mesaj attınız. Çok yoğun — koçun telefonu "
            "veliler tarafından engellenebilir veya WhatsApp tarafından "
            "spam'a düşebilir.",
        )
    if today_count >= WARN_DAILY_BUSY:
        return (
            "yogun",
            f"Bugün {today_count} mesaj attınız. Velileri yormamaya dikkat — "
            "ardışık mesajlar engellenebilir.",
        )
    return ("ok", None)


def compute_dispatch_stats(db: Session, *, sender: User) -> DispatchStats:
    """Sender'ın bugün ve bu hafta gönderim sayıları + uyarı."""
    now = datetime.now(timezone.utc)
    today_start = _utc_today_start(now)
    week_start = _utc_week_start(now)

    today_count: int = (
        db.query(func.count(WhatsAppDispatchLog.id))
        .filter(
            WhatsAppDispatchLog.sender_user_id == sender.id,
            WhatsAppDispatchLog.created_at >= today_start,
        )
        .scalar()
        or 0
    )
    week_count: int = (
        db.query(func.count(WhatsAppDispatchLog.id))
        .filter(
            WhatsAppDispatchLog.sender_user_id == sender.id,
            WhatsAppDispatchLog.created_at >= week_start,
        )
        .scalar()
        or 0
    )

    level, message = _warning_for(today_count)

    return DispatchStats(
        today_count=today_count,
        week_count=week_count,
        week_start_iso=week_start.date().isoformat(),
        warning_level=level,
        warning_message=message,
    )
