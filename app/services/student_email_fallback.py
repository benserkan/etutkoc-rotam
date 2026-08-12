"""Öğrenci e-posta fallback'i — kayıtlı mobil cihazı OLMAYAN öğrenciye kritik
olaylarda e-posta (2026-08-12 kullanıcı kararı).

Gerekçe: uygulama store'da yayınlanana kadar push fiilen ulaşmıyor; cihazsız
öğrencinin tek kanalı e-posta. KURAL: cihaz kayıtlıysa YALNIZ push (çift
bildirim olmaz); cihaz yoksa e-posta. Kapsanan olaylar:
  - Yeni haftalık program yayını (publish-week + "Veliye duyur")   → burada
  - Haftalık gelişim özeti (günlük cron `student_weekly_email`)    → burada
  - Anket ataması                                                  → surveys.py
  - Talep yanıtı                                                   → request_service

Dürüstlük: gönderim DAİMA `email_service.send_email` üzerinden — SMTP dönüşü
comm_log'a yazılır (sent/failed), İletişim Sağlığı panelinde izlenir. Dedup da
comm_log üzerinden yapılır; ayrı tablo/migration gerekmez.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import User
from app.models.communication_log import CommunicationLog
from app.models.device_push_token import DevicePushToken
from app.models.task import Task
from app.models.user import UserRole
from app.services.email_service import send_email

logger = logging.getLogger("app.student_email_fallback")

CATEGORY_NEW_PROGRAM = "student_new_program"
CATEGORY_WEEKLY_SUMMARY = "student_weekly_summary"

# Dedup pencereleri — veli akışıyla aynı semantik (new_program 24s, weekly 6g).
NEW_PROGRAM_DEDUP = timedelta(hours=24)
WEEKLY_DEDUP = timedelta(days=6)


def _has_device(db: Session, user_id: int) -> bool:
    return (
        db.query(DevicePushToken.id)
        .filter(DevicePushToken.user_id == user_id)
        .first()
        is not None
    )


def _recent_email_exists(
    db: Session, *, to_address: str, category: str, within: timedelta,
) -> bool:
    """Dedup: aynı adrese aynı kategoride pencere içinde kayıt var mı?

    'sent' + 'delivered' + dev 'suppressed' sayılır (dev'de çift log birikmesin);
    'failed' SAYILMAZ — başarısız deneme yeni denemeyi engellememeli.
    """
    cutoff = datetime.now(timezone.utc) - within
    return (
        db.query(CommunicationLog.id)
        .filter(
            CommunicationLog.channel == "email",
            CommunicationLog.to_address == to_address,
            CommunicationLog.category == category,
            CommunicationLog.created_at >= cutoff,
            CommunicationLog.status != "failed",
        )
        .first()
        is not None
    )


def _student_guard(db: Session, student: User, *, category: str, within: timedelta) -> str | None:
    """Ortak kapılar — None dönerse gönderilebilir, aksi halde atlama nedeni."""
    email = (student.email or "").strip()
    if "@" not in email or email.endswith("@kvkk.local"):
        return "no_email"
    if not student.is_active:
        return "inactive"
    if _has_device(db, student.id):
        return "has_device"  # push kanalı canlı — e-posta ATILMAZ (çift bildirim yok)
    if _recent_email_exists(db, to_address=email, category=category, within=within):
        return "recent"
    return None


# =============================================================================
# 1) Yeni haftalık program → öğrenci e-postası
# =============================================================================


def send_student_new_program(
    db: Session, *, student: User, week_start: date, week_end: date,
) -> str:
    """Hafta yayınlanınca cihazsız öğrenciye program e-postası. Dönen değer
    durum kodu (test + log için): sent / failed / no_email / inactive /
    has_device / recent / no_tasks.
    """
    skip = _student_guard(
        db, student, category=CATEGORY_NEW_PROGRAM, within=NEW_PROGRAM_DEDUP,
    )
    if skip:
        return skip

    from app.services.notification_producers import (
        _build_daily_breakdown,
        _get_recent_exams,
    )

    daily = _build_daily_breakdown(
        db, student_id=student.id, week_start=week_start, week_end=week_end,
    )
    total_tasks = sum(d.get("gorev_total") or 0 for d in daily)
    if total_tasks <= 0:
        return "no_tasks"

    ctx = {
        "student_name": student.full_name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_tasks": total_tasks,
        "daily_breakdown": daily,
        "recent_exams": _get_recent_exams(db, student_id=student.id),
    }
    ok = send_email(student.email, CATEGORY_NEW_PROGRAM, ctx)
    return "sent" if ok else "failed"


def send_student_new_program_bg(
    student_id: int, week_start_iso: str, week_end_iso: str,
) -> None:
    """BackgroundTasks sarmalayıcısı — taze session (istek oturumu kapanmış olur).

    SMTP 2-5 sn sürebilir; koçun publish isteğini BLOKLAMAZ. Best-effort:
    hata loglanır, asla raise edilmez (comm_log 'failed' zaten iz bırakır).
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        student = db.get(User, student_id)
        if student is None or student.role != UserRole.STUDENT:
            return
        result = send_student_new_program(
            db,
            student=student,
            week_start=date.fromisoformat(week_start_iso),
            week_end=date.fromisoformat(week_end_iso),
        )
        logger.info(
            "student_new_program e-posta: student=%s → %s", student_id, result,
        )
    except Exception:
        logger.exception("student_new_program e-posta hatası student=%s", student_id)
    finally:
        db.close()


# =============================================================================
# 2) Haftalık gelişim özeti → öğrenci e-postası (cron)
# =============================================================================


def send_student_weekly_summary(
    db: Session, *, student: User, week_start: date, week_end: date,
) -> str:
    """Cihazsız öğrenciye haftalık gelişim özeti (veli haftalık raporunun
    öğrenciye hitap eden hâli; AYNI veri üreticisi — sayılar birebir tutarlı).
    """
    skip = _student_guard(
        db, student, category=CATEGORY_WEEKLY_SUMMARY, within=WEEKLY_DEDUP,
    )
    if skip:
        return skip

    from app.services.notification_producers import (
        _build_daily_breakdown,
        _get_latest_exam,
    )

    daily = _build_daily_breakdown(
        db, student_id=student.id, week_start=week_start, week_end=week_end,
    )
    gorev_total = sum(d.get("gorev_total") or 0 for d in daily)
    if gorev_total <= 0:
        return "no_tasks"
    gorev_done = sum(d.get("gorev_done") or 0 for d in daily)
    test_planned = sum(d.get("test_planned") or 0 for d in daily)
    test_completed = sum(d.get("test_completed") or 0 for d in daily)
    deneme = sum(d.get("deneme_count") or 0 for d in daily)

    ctx = {
        "student_name": student.full_name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "gorev_total": gorev_total,
        "gorev_done": gorev_done,
        "gorev_rate": round(100 * gorev_done / gorev_total) if gorev_total else 0,
        "test_planned": test_planned,
        "test_completed": test_completed,
        "deneme_count": deneme,
        "daily_breakdown": daily,
        "latest_exam": _get_latest_exam(db, student_id=student.id, since_days=7),
    }
    ok = send_email(student.email, CATEGORY_WEEKLY_SUMMARY, ctx)
    return "sent" if ok else "failed"


def run_student_weekly_emails(db: Session, *, now: datetime) -> dict:
    """Cron `student_weekly_email` (günlük, sabah) — son 7 günde görevi olan
    AKTİF öğrencilere haftalık özet. 6 günlük dedup sayesinde fiilen haftada 1.

    Veli bağı ARANMAZ — velisiz öğrenci de alır (2026-08-12 Hatice vakası:
    kiracıda hiç veli yoktu → hiçbir bildirim doğmuyordu).
    """
    today = now.astimezone(timezone.utc).date()
    week_start = today - timedelta(days=7)
    week_end = today - timedelta(days=1)  # dünle biten tam 7 gün

    students = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.teacher_id.isnot(None),
        )
        .all()
    )
    counts: dict[str, int] = {}
    for s in students:
        any_task = (
            db.query(Task.id)
            .filter(
                Task.student_id == s.id,
                Task.date >= week_start,
                Task.date <= week_end,
                Task.is_draft.is_(False),
            )
            .first()
        )
        if not any_task:
            counts["no_tasks"] = counts.get("no_tasks", 0) + 1
            continue
        result = send_student_weekly_summary(
            db, student=s, week_start=week_start, week_end=week_end,
        )
        counts[result] = counts.get(result, 0) + 1
    logger.info("student_weekly_email cron: %s", counts)
    return counts
