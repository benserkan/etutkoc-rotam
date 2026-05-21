"""Olay-tabanlı bildirim tetikleyicileri.

Cron job'lar (cron_jobs.py) "saatte bir tara, eşleşeni gönder" mantığı; bu modül
"X olayı oldu, ilgili bildirimleri hemen üret" mantığı. Cron'lar backstop görevi
görür — event tetikleyici düşse de gece 23:55 weekly_backstop yakalar.

Public API:
    on_task_completed(db, student) — döngü tamamlandıysa weekly_report enqueue
    on_program_published(db, student, week_start) — new_program enqueue
    on_teacher_note_created(db, note) — note'a bağlı tüm velilere teacher_note

Tasarım kuralları:
- Tüm linkli velilere yayılır (parent_student_links → her veli için ayrı log)
- Dedup: producer'lar zaten kuyruğa yazıyor; tetikleyici öncesi `_has_recent_*`
  kontrolü ile aynı olay için çift bildirim engellenir
- Bildirimler enqueue edilir, dispatcher gönderir (event handler senkron blocking
  HTTP isteği yapmaz — bu önemli, response süresini uzatmaz)
- Hata durumunda exception YUTULMAZ ama logger'a yazılır + caller commit etmemiş
  olabilir; çağıran (route handler) commit'i kendi yapar
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import (
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentStudentLink,
    Task,
    TaskBookItem,
    TaskStatus,
    TeacherNoteToParent,
    User,
    UserRole,
)
from app.services.analytics import week_stats_for
from app.services.notification_producers import (
    produce_new_program,
    produce_teacher_note,
    produce_weekly_report,
)


logger = logging.getLogger(__name__)


# ---------------------------- Yardımcılar ----------------------------

def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _active_parents_for(db: Session, student_id: int) -> list[User]:
    """Bu öğrenciye bağlı, aktif PARENT kullanıcıları.

    Pasif (is_paused=True) olanlar bildirim almaz — listeye girmez.
    Ayrıca öğrencinin kendisi pasifse boş liste döner; o öğrenci için
    hiç event-tetikli bildirim gitmez. Single point of control: tüm
    on_* fonksiyonları bu helper'ı kullanır.
    """
    student = db.get(User, student_id)
    if student is None or student.is_paused:
        return []
    links = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.parent))
        .filter(ParentStudentLink.student_id == student_id)
        .all()
    )
    out = []
    for link in links:
        p = link.parent
        if p and p.is_active and not p.is_paused and p.role == UserRole.PARENT:
            out.append(p)
    return out


def _has_recent(
    db: Session, *, parent_id: int, student_id: int,
    kind: NotificationKind, within: timedelta,
) -> bool:
    """Aynı veliye/öğrenciye/türe son N süre içinde QUEUED/SENT bildirim var mı?"""
    cutoff = datetime.now(timezone.utc) - within
    return (
        db.query(NotificationLog)
        .filter(
            NotificationLog.parent_id == parent_id,
            NotificationLog.student_id == student_id,
            NotificationLog.kind == kind,
            NotificationLog.status.in_([
                NotificationStatus.SENT, NotificationStatus.QUEUED,
            ]),
            NotificationLog.queued_at >= cutoff,
        )
        .first()
        is not None
    )


# ---------------------------- on_task_completed ----------------------------


def _is_cycle_complete(db: Session, student_id: int, today: date) -> bool:
    """Öğrencinin son 7 günündeki tüm görevler tamamlandı mı?

    Döngü = bugün dahil son 7 gün (ya da öğrencinin son seansından bugüne).
    Eğer pencerede:
      - hiç görev yoksa → False (rapor anlamsız)
      - en az 1 PENDING/PARTIAL görev varsa → False
    Aksi (tüm görevler COMPLETED) → True.
    """
    week_start = today - timedelta(days=6)
    tasks = (
        db.query(Task)
        .filter(
            Task.student_id == student_id,
            Task.date >= week_start,
            Task.date <= today,
        )
        .all()
    )
    if not tasks:
        return False
    for t in tasks:
        if t.status != TaskStatus.COMPLETED:
            return False
    return True


def on_task_completed(db: Session, student: User) -> dict:
    """Öğrenci bir görevi (veya kalemini) tamamlayıp görev COMPLETED'a geçtikten
    sonra çağrılır.

    Döngü tamamlandıysa (son 7 gün hepsi COMPLETED) ilgili velilere weekly_report
    üretir. Aksi halde no-op. Backstop cron her durumda 23:55'te tarar.

    Çağrıyı yapan route'un commit etmesi beklenir.
    """
    summary = {"checked": 1, "fired_for_parents": 0, "skipped_recent": 0, "skipped_no_cycle": 0}

    today = _today_utc()
    if not _is_cycle_complete(db, student.id, today):
        summary["skipped_no_cycle"] = 1
        return summary

    parents = _active_parents_for(db, student.id)
    if not parents:
        return summary

    week_start = today - timedelta(days=6)
    wstats = week_stats_for(db, student.id, today)
    rate = (
        int(round(100 * wstats.completed / wstats.planned))
        if wstats.planned > 0 else None
    )

    for parent in parents:
        # Dedup — aynı öğrenci için son 6 günde haftalık rapor gönderilmiş mi?
        if _has_recent(
            db, parent_id=parent.id, student_id=student.id,
            kind=NotificationKind.WEEKLY_REPORT, within=timedelta(days=6),
        ):
            summary["skipped_recent"] += 1
            continue

        produce_weekly_report(
            db, parent=parent, student=student,
            week_start=week_start, week_end=today,
            completed=wstats.completed, planned=wstats.planned, rate_pct=rate,
        )
        summary["fired_for_parents"] += 1

    if summary["fired_for_parents"]:
        logger.info("on_task_completed → weekly_report fired: %s", summary)
    return summary


# ---------------------------- on_program_published ----------------------------


def on_program_published(
    db: Session,
    *,
    student: User,
    week_start: date,
    week_end: date | None = None,
) -> dict:
    """Öğretmen "Programı veliye duyur" butonuna bastığında çağrılır.

    Önümüzdeki 7 günün toplam görev sayısı + günlük dağılımı hesaplanır,
    new_program bildirimi her aktif veliye yayılır. Dedup: aynı öğrenci için
    24 saat içinde NEW_PROGRAM gönderildiyse atla (çift duyuru olmasın).
    """
    if week_end is None:
        week_end = week_start + timedelta(days=6)

    summary = {"fired": 0, "skipped_recent": 0, "no_tasks": False}

    days = [week_start + timedelta(days=i) for i in range((week_end - week_start).days + 1)]
    # Sadece yayınlanmış görevler veli duyurusuna girer — taslaklar görmezden gelinir.
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student.id,
            Task.date >= week_start,
            Task.date <= week_end,
            Task.is_draft.is_(False),
        )
        .all()
    )
    if not tasks:
        summary["no_tasks"] = True
        logger.info("on_program_published: %s için bu pencerede görev yok", student.id)
        return summary

    total_tasks = len(tasks)
    by_day: dict[date, int] = {d: 0 for d in days}
    for t in tasks:
        if t.date in by_day:
            by_day[t.date] += 1

    weekday_labels = [
        "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
    ]
    daily_breakdown = [
        {
            "date": d.isoformat(),
            "label": weekday_labels[d.weekday()],
            "task_count": by_day[d],
        }
        for d in days
    ]

    parents = _active_parents_for(db, student.id)
    for parent in parents:
        if _has_recent(
            db, parent_id=parent.id, student_id=student.id,
            kind=NotificationKind.NEW_PROGRAM, within=timedelta(hours=24),
        ):
            summary["skipped_recent"] += 1
            continue

        produce_new_program(
            db, parent=parent, student=student,
            week_start=week_start, week_end=week_end,
            total_tasks=total_tasks, daily_breakdown=daily_breakdown,
        )
        summary["fired"] += 1

    logger.info("on_program_published → new_program: %s", summary)
    return summary


# ---------------------------- on_teacher_note_created ----------------------------


def on_teacher_note_created(db: Session, note: TeacherNoteToParent) -> dict:
    """Öğretmen veliye not göndermek istediğinde, TeacherNoteToParent kaydı
    oluşturulduktan sonra çağrılır.

    İlgili öğrencinin tüm aktif velilerine teacher_note bildirimi yayılır.
    Dedup YOK — aynı içerikli birden fazla not gönderilebilir, her biri
    ayrı bir bildirim. note.delivered_at set edilir.
    """
    student = db.get(User, note.student_id)
    teacher = db.get(User, note.teacher_id)
    if not student or not teacher:
        logger.warning("on_teacher_note_created: student/teacher bulunamadı (note=%s)", note.id)
        return {"fired": 0, "error": "missing_user"}

    parents = _active_parents_for(db, student.id)
    if not parents:
        logger.info("on_teacher_note_created: %s için aktif veli yok", student.id)
        return {"fired": 0}

    summary = {"fired": 0}
    for parent in parents:
        produce_teacher_note(
            db, parent=parent, student=student, teacher=teacher,
            body=note.body, note_id=note.id,
        )
        summary["fired"] += 1

    note.delivered_at = datetime.now(timezone.utc)
    logger.info("on_teacher_note_created → teacher_note: %s", summary)
    return summary
