"""Stage 7 — Sistem sağlık göstergeleri.

Süper admin '/admin/system-health' sayfasında şunları görür:
- Cron job'ların son çalışma + durum + program
- Notification dispatcher: bekleyen sayım + en eski + son tur özeti
- DB: tablo başına satır sayısı + dosya boyutu
- Disk uyarısı: > 500MB sarı, > 1GB kırmızı

Performans: tüm metrikler tek seferde toplanır; sayfa <500ms hedef.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AdminWeeklyDigest,
    AuditLog,
    CreditAccount,
    CronSchedule,
    Institution,
    NotificationLog,
    NotificationStatus,
    UsageEvent,
    User,
)


logger = logging.getLogger(__name__)


# Disk kullanım eşikleri (MB cinsinden)
DISK_WARN_MB = 500
DISK_CRIT_MB = 1000

# Cron sağlık eşiği — son çalışma bu süreden eski ise sarı/kırmızı
CRON_STALE_HOURS_WARN = 25      # 25h (günlük cron için)
CRON_STALE_HOURS_CRIT = 48      # 48h (kesin sorun)


@dataclass
class CronStatus:
    schedule: CronSchedule
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    hours_since_run: float | None
    health: str   # 'ok' | 'warn' | 'crit' | 'never' | 'disabled'


@dataclass
class DispatcherStatus:
    queued_count: int
    failed_count: int
    oldest_queued_at: datetime | None
    oldest_queued_age_hours: float | None
    health: str   # 'ok' | 'warn' | 'crit'


@dataclass
class DatabaseStatus:
    file_path: str | None
    file_size_mb: float | None
    table_counts: dict[str, int]
    health: str   # 'ok' | 'warn' | 'crit'


@dataclass
class BackupStatus:
    """Postgres yedek (pg_dump) sağlık durumu — cron + rotasyon takibi."""
    backup_dir: str
    latest_at: datetime | None         # son yedek dosyasının mtime'ı
    latest_age_hours: float | None     # son yedekten kaç saat geçti
    latest_size_mb: float | None       # son yedek dosyasının boyutu
    total_count: int                   # toplam yedek dosyası sayısı
    total_size_mb: float               # toplam disk kullanımı (yedek dizini)
    health: str                        # 'ok' (<30h) | 'warn' (30-48h) | 'crit' (>48h veya yedek yok)


@dataclass
class SystemHealthSnapshot:
    crons: list[CronStatus] = field(default_factory=list)
    dispatcher: DispatcherStatus | None = None
    database: DatabaseStatus | None = None
    backup: BackupStatus | None = None
    overall_health: str = "ok"  # 'ok' | 'warn' | 'crit'


def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _cron_health(
    schedule: CronSchedule, now: datetime,
) -> tuple[float | None, str]:
    """Cron son çalışma zamanına göre sağlık seviyesi."""
    if not schedule.enabled:
        return (None, "disabled")
    last = _normalize_dt(schedule.last_run_at)
    if last is None:
        return (None, "never")
    hours = (now - last).total_seconds() / 3600
    # day_of_week NULL = günlük; aksi haftalık
    is_weekly = schedule.day_of_week is not None
    warn_h = (24 * 7 + 1) if is_weekly else CRON_STALE_HOURS_WARN
    crit_h = (24 * 8) if is_weekly else CRON_STALE_HOURS_CRIT
    if hours >= crit_h:
        return (hours, "crit")
    if hours >= warn_h:
        return (hours, "warn")
    return (hours, "ok")


def collect_cron_status(db: Session, *, now: datetime | None = None) -> list[CronStatus]:
    if now is None:
        now = datetime.now(timezone.utc)
    schedules = db.query(CronSchedule).order_by(CronSchedule.job_key).all()
    out: list[CronStatus] = []
    for s in schedules:
        hours, health = _cron_health(s, now)
        out.append(CronStatus(
            schedule=s,
            last_run_at=_normalize_dt(s.last_run_at),
            last_status=s.last_status,
            last_error=s.last_error,
            hours_since_run=hours,
            health=health,
        ))
    return out


def collect_dispatcher_status(
    db: Session, *, now: datetime | None = None,
) -> DispatcherStatus:
    if now is None:
        now = datetime.now(timezone.utc)
    queued = (
        db.query(func.count(NotificationLog.id))
        .filter(NotificationLog.status == NotificationStatus.QUEUED)
        .scalar() or 0
    )
    failed = (
        db.query(func.count(NotificationLog.id))
        .filter(NotificationLog.status == NotificationStatus.FAILED)
        .scalar() or 0
    )
    oldest_dt = (
        db.query(func.min(NotificationLog.queued_at))
        .filter(NotificationLog.status == NotificationStatus.QUEUED)
        .scalar()
    )
    oldest_dt = _normalize_dt(oldest_dt)
    age_hours = None
    if oldest_dt:
        age_hours = (now - oldest_dt).total_seconds() / 3600
    # Sağlık: 100+ pending veya en eski 6h+ → warn; 500+ veya 24h+ → crit
    if queued >= 500 or (age_hours is not None and age_hours >= 24):
        health = "crit"
    elif queued >= 100 or (age_hours is not None and age_hours >= 6):
        health = "warn"
    else:
        health = "ok"
    return DispatcherStatus(
        queued_count=int(queued),
        failed_count=int(failed),
        oldest_queued_at=oldest_dt,
        oldest_queued_age_hours=age_hours,
        health=health,
    )


def collect_database_status(db: Session) -> DatabaseStatus:
    # Önemli tablolar (system tablo değil — domain tabloları)
    interesting = [
        ("users", User),
        ("institutions", Institution),
        ("audit_logs", AuditLog),
        ("notification_logs", NotificationLog),
        ("admin_weekly_digests", AdminWeeklyDigest),
        ("usage_events", UsageEvent),
        ("credit_accounts", CreditAccount),
    ]
    counts: dict[str, int] = {}
    for label, model in interesting:
        try:
            n = db.query(func.count(model.id)).scalar() or 0
            counts[label] = int(n)
        except Exception as e:
            logger.warning("table count failed for %s: %s", label, e)
            counts[label] = -1

    # SQLite dosya boyutu (file:/// path)
    file_path = None
    file_size_mb = None
    try:
        url = str(settings.database_url)
        if url.startswith("sqlite:///"):
            file_path = url.replace("sqlite:///", "", 1)
            # Relative → absolute
            p = Path(file_path)
            if not p.is_absolute():
                p = Path.cwd() / p
            file_path = str(p)
            if p.exists():
                file_size_mb = round(p.stat().st_size / (1024 * 1024), 2)
    except Exception as e:
        logger.warning("DB file inspect failed: %s", e)

    # Sağlık: dosya boyutu eşiklerine göre
    health = "ok"
    if file_size_mb is not None:
        if file_size_mb >= DISK_CRIT_MB:
            health = "crit"
        elif file_size_mb >= DISK_WARN_MB:
            health = "warn"

    return DatabaseStatus(
        file_path=file_path,
        file_size_mb=file_size_mb,
        table_counts=counts,
        health=health,
    )


def collect_backup_status(*, now: datetime | None = None) -> BackupStatus:
    """`/opt/etutkoc/backups/lgs-*.dump` (varsayılan) içinden son yedeği bulur.

    Yol BACKUP_DIR env değişkeniyle özelleştirilebilir. Eşikler:
      - ≤30h: ok (cron 03:00 UTC, +27h tolerans)
      - 30-48h: warn (1 gün cron atlamış olabilir)
      - >48h veya hiç yedek yok: crit
    """
    if now is None:
        now = datetime.now(timezone.utc)
    backup_dir = os.environ.get("BACKUP_DIR", "/opt/etutkoc/backups")
    p = Path(backup_dir)
    if not p.exists():
        return BackupStatus(
            backup_dir=backup_dir,
            latest_at=None, latest_age_hours=None, latest_size_mb=None,
            total_count=0, total_size_mb=0.0, health="crit",
        )
    try:
        files = list(p.glob("lgs-*.dump"))
    except OSError:
        return BackupStatus(
            backup_dir=backup_dir,
            latest_at=None, latest_age_hours=None, latest_size_mb=None,
            total_count=0, total_size_mb=0.0, health="crit",
        )
    if not files:
        return BackupStatus(
            backup_dir=backup_dir,
            latest_at=None, latest_age_hours=None, latest_size_mb=None,
            total_count=0, total_size_mb=0.0, health="crit",
        )
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest = files[0]
    latest_mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
    age_h = (now - latest_mtime).total_seconds() / 3600.0
    total_size = sum(f.stat().st_size for f in files)

    if age_h <= 30:
        health = "ok"
    elif age_h <= 48:
        health = "warn"
    else:
        health = "crit"

    return BackupStatus(
        backup_dir=backup_dir,
        latest_at=latest_mtime,
        latest_age_hours=round(age_h, 1),
        latest_size_mb=round(latest.stat().st_size / 1024.0 / 1024.0, 2),
        total_count=len(files),
        total_size_mb=round(total_size / 1024.0 / 1024.0, 2),
        health=health,
    )


def collect_snapshot(db: Session, *, now: datetime | None = None) -> SystemHealthSnapshot:
    if now is None:
        now = datetime.now(timezone.utc)
    crons = collect_cron_status(db, now=now)
    dispatcher = collect_dispatcher_status(db, now=now)
    database = collect_database_status(db)
    backup = collect_backup_status(now=now)

    # Overall — en kötü bileşen
    levels = ["ok", "warn", "crit"]
    worst = "ok"
    for c in crons:
        if c.health in levels and levels.index(c.health) > levels.index(worst):
            worst = c.health
    if dispatcher.health in levels and levels.index(dispatcher.health) > levels.index(worst):
        worst = dispatcher.health
    if database.health in levels and levels.index(database.health) > levels.index(worst):
        worst = database.health
    if backup.health in levels and levels.index(backup.health) > levels.index(worst):
        worst = backup.health

    return SystemHealthSnapshot(
        crons=crons,
        dispatcher=dispatcher,
        database=database,
        backup=backup,
        overall_health=worst,
    )
