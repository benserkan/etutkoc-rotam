"""Cron runner — CronSchedule satırlarına bakıp due olanları çalıştırır.

Tek public fonksiyon: `tick(db, now)`. Her aktif schedule için:
1. day_of_week eşleşiyor mu (NULL = her gün)
2. Bugünün scheduled saati geçti mi (now >= today HH:MM)
3. Bu instance daha önce çalıştırıldı mı (last_run_at >= scheduled_today)

Eğer (1)+(2) ✓ ve (3) ✗ ise job çağrılır; sonuç last_run_at + last_status'a yazılır.

Catch-up: Servis 22:00'da kalktıysa ve daily_summary 21:00'a planlıysa,
  scheduled_today = today 21:00, now = 22:00, last_run_at < today 21:00 → çalışır.
  Ama yarın 21:00 geçince yine çalışır (yeni instance).

Multi-day catch-up: Sadece "bugünün instance'ı" çalıştırılır, geçen günlerinki kaybedilir.
  (Bu kasıtlı; haftalık özetin 3 hafta önceki instance'ını geçmiş için göndermek
  anlamlı değil.)

Çağrılma yerleri:
- Dev: main.py lifespan'inde dispatcher loop her tick'inde
- Prod: dispatcher CLI loop'unda her tick'inde
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import CronSchedule
from app.services.cron_jobs import JOB_REGISTRY


logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_due(sch: CronSchedule, now: datetime) -> bool:
    """Bu schedule şu anda due mı?

    İki mod:
      - interval_minutes dolu → "her N dakikada bir" (last_run_at + N <= now)
      - interval_minutes NULL → "günde 1 kez HH:MM" (klasik davranış)
    """
    if not sch.enabled:
        return False

    # Katman 11.J — interval modu
    interval = getattr(sch, "interval_minutes", None)
    if interval is not None and interval > 0:
        if sch.last_run_at is None:
            return True  # hiç çalışmamış → hemen tetikle
        last = sch.last_run_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed_seconds = (now - last).total_seconds()
        return elapsed_seconds >= interval * 60

    # Klasik mod: günde 1 kez HH:MM
    # day_of_week: 0=Pzt..6=Paz; NULL = her gün. Python weekday() de 0=Pzt.
    if sch.day_of_week is not None and now.weekday() != sch.day_of_week:
        return False
    scheduled_today = now.replace(
        hour=sch.hour, minute=sch.minute, second=0, microsecond=0
    )
    if now < scheduled_today:
        return False
    if sch.last_run_at is not None:
        last = sch.last_run_at
        # SQLite naive datetime dönebilir → UTC kabul et
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last >= scheduled_today:
            return False
    return True


def tick(db: Session, now: datetime | None = None, *, force: bool = False) -> dict[str, dict]:
    """Bütün cron job'ları kontrol et, due olanları çalıştır.

    force=True: schedule kontrolünü atla, enabled olan tüm job'ları zorla çalıştır
    (manuel "Şimdi çalıştır" akışında kullanılır).

    Returns: {job_key: result_summary}.
    """
    if now is None:
        now = _now_utc()

    schedules = db.query(CronSchedule).all()
    results: dict[str, dict] = {}

    for sch in schedules:
        if force:
            if not sch.enabled:
                continue
        elif not is_due(sch, now):
            continue

        job_fn = JOB_REGISTRY.get(sch.job_key)
        if job_fn is None:
            sch.last_run_at = now
            sch.last_status = "skipped"
            sch.last_error = f"unknown_job_key:{sch.job_key}"
            logger.warning("Bilinmeyen cron job_key: %s", sch.job_key)
            db.commit()
            continue

        try:
            summary = job_fn(db, now=now)
            sch.last_run_at = now
            sch.last_status = "success"
            sch.last_error = None
            results[sch.job_key] = summary
            db.commit()
            logger.info("cron %s: %s", sch.job_key, summary)
        except Exception as e:
            sch.last_run_at = now  # tekrar tekrar denemesin diye yine yazılır
            sch.last_status = "failed"
            sch.last_error = str(e)[:500]
            results[sch.job_key] = {"error": str(e)}
            db.commit()
            logger.exception("cron job %s başarısız: %s", sch.job_key, e)

    return results
