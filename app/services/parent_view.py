"""Veliye özel veri toplayıcı — gizlilik-güvenli görünüm.

Tek kapı: parent_id + student_id verir, "veli için güvenli" dict döner. Eğer
veli o öğrenciye bağlı değilse PermissionError.

KVKK GİZLİLİK SINIRI:
- Paylaşılan: tamamlanan/atlanan görev sayısı, tipi, ders bazında toplam/çözülen
  sayıları, streak, tamamlama oranı, projeksiyon (hedef tutuyor mu),
  "iletilebilir" işaretli öğretmen notları (TeacherNoteToParent).
- Paylaşılmayan: deneme net/puan, konu bazında %doğru-yanlış, öğrenci-öğretmen
  mesajları (TaskRequest), AI öneri motoru iç işleyişi.

MOBİL HAZIRLIĞI:
- Bu service'in dönüş değerleri JSON-serializable saf dict/list — sonra mobil
  için /api/parent/... rotaları aynı çıktıyı `return data` ile döner.
- Tarihler ISO formatı; SQLAlchemy entity sızdırmıyor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    NotificationLog,
    NotificationKind,
    ParentStudentLink,
    Task,
    TaskBookItem,
    TaskStatus,
    TeacherNoteToParent,
    User,
    UserRole,
)
from app.models.book import BookSection
from app.models.curriculum import Topic
from app.services.analytics import (
    daily_completed_series,
    daily_planned_series,
    student_snapshot,
    subject_breakdown,
)


class ParentAccessDenied(Exception):
    """Veli bu öğrenciye bağlı değil — KVKK ihlali girişimi."""


def assert_parent_can_view(db: Session, parent: User, student_id: int) -> User:
    """KVKK guard: veli bu öğrenciye gerçekten bağlı mı? Bağlıysa Student döner."""
    if parent.role != UserRole.PARENT:
        raise ParentAccessDenied("Sadece veliler için.")

    link = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.student).joinedload(User.academic_year))
        .filter(
            ParentStudentLink.parent_id == parent.id,
            ParentStudentLink.student_id == student_id,
        )
        .first()
    )
    if not link or not link.student or link.student.role != UserRole.STUDENT:
        raise ParentAccessDenied("Bu öğrenciye erişim yetkiniz yok.")
    return link.student


def list_parent_students(db: Session, parent: User) -> list[dict[str, Any]]:
    """Veliye bağlı tüm öğrenciler — dashboard kartları için."""
    if parent.role != UserRole.PARENT:
        return []

    today = date.today()
    links = (
        db.query(ParentStudentLink)
        .options(
            joinedload(ParentStudentLink.student).joinedload(User.academic_year),
        )
        .filter(ParentStudentLink.parent_id == parent.id)
        .all()
    )
    from app.services import gorev_stats
    _wk_start = today - timedelta(days=6)
    _opts = joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject)
    out = []
    for link in links:
        s = link.student
        if not s or s.role != UserRole.STUDENT:
            continue
        # Koçluğu sonlandırılmış (pasif) çocuk → minimal kart: "Koçluk sona erdi"
        # rozeti için is_active=False, güncel metrikler sıfır/None (bayat takip
        # gösterme). Geçmiş raporlar/denemeler ayrı sayfadan erişilebilir. Ağır
        # snapshot/görev sorgusu yapılmaz.
        if not s.is_active:
            out.append({
                "student_id": s.id,
                "full_name": s.full_name,
                "grade_level": s.grade_level,
                "is_graduate": s.is_graduate,
                "display_grade_label": s.display_grade_label,
                "academic_year": s.academic_year.name if s.academic_year else None,
                "exam_date": s.effective_exam_date.isoformat() if s.effective_exam_date else None,
                "exam_label": s.effective_exam_label,
                "exam_target": s.effective_exam_target.lower() if s.effective_exam_target else "none",
                "relation": link.relation.value if link.relation else None,
                "is_primary": link.is_primary,
                "is_active": False,
                "today_planned": 0, "today_completed": 0,
                "week_planned": 0, "week_completed": 0, "week_completion_rate": None,
                "today_gorev_total": 0, "today_gorev_done": 0,
                "week_gorev_total": 0, "week_gorev_done": 0, "week_gorev_rate": None,
                "week_test_planned": 0, "week_test_completed": 0,
                "rate_7d": None, "consistency_7d": None,
                "warning_level": "green",
            })
            continue
        snap = student_snapshot(db, s, today=today)
        # 7 günlük tamamlama (bu hafta için)
        week = snap.week
        # GÖREV-bazlı (görev/test/deneme AYRI; deneme soruları test'e karışmaz)
        _wk_tasks = (
            db.query(Task).options(_opts)
            .filter(Task.student_id == s.id, Task.date >= _wk_start,
                    Task.date <= today, Task.is_draft.is_(False))
            .all()
        )
        _gw = gorev_stats.summarize(_wk_tasks)
        _gt = gorev_stats.summarize([t for t in _wk_tasks if t.date == today])
        out.append({
            "student_id": s.id,
            "full_name": s.full_name,
            "grade_level": s.grade_level,
            "is_graduate": s.is_graduate,
            "display_grade_label": s.display_grade_label,
            "academic_year": s.academic_year.name if s.academic_year else None,
            "exam_date": s.effective_exam_date.isoformat() if s.effective_exam_date else None,
            "exam_label": s.effective_exam_label,
            "exam_target": s.effective_exam_target.lower() if s.effective_exam_target else "none",
            "relation": link.relation.value if link.relation else None,
            "is_primary": link.is_primary,
            "is_active": True,
            "today_planned": snap.today.planned,
            "today_completed": snap.today.completed,
            "week_planned": week.planned,
            "week_completed": week.completed,
            "week_completion_rate": (
                round(100 * week.completed / week.planned)
                if week.planned > 0 else None
            ),
            # GÖREV-bazlı (her madde 1 görev; deneme/test/etkinlik AYRI)
            "today_gorev_total": _gt.gorev_total,
            "today_gorev_done": _gt.gorev_done,
            "week_gorev_total": _gw.gorev_total,
            "week_gorev_done": _gw.gorev_done,
            "week_gorev_rate": (
                round(100 * _gw.gorev_done / _gw.gorev_total)
                if _gw.gorev_total > 0 else None
            ),
            "week_test_planned": _gw.test_planned,       # yalnız soru bankası
            "week_test_completed": _gw.test_completed,
            # "Son 7 Gün Oran" = planlanan→tamamlanan oranı (hit_rate_7d, 0..1).
            # DİKKAT: rate_7d test/gün HIZIDIR (yüzde değil) — burada kullanılmaz.
            "rate_7d": (
                min(100, round(snap.hit_rate_7d * 100))
                if snap.hit_rate_7d is not None else None
            ),
            "consistency_7d": round(snap.consistency_7d * 100) if snap.consistency_7d is not None else None,
            "warning_level": snap.worst_warning_level,
        })
    return out


def student_overview(db: Session, parent: User, student_id: int) -> dict[str, Any]:
    """Veliye gösterilecek öğrenci özet sayfası verisi.

    Raises ParentAccessDenied if parent not linked.
    """
    student = assert_parent_can_view(db, parent, student_id)
    today = date.today()

    snap = student_snapshot(db, student, today=today)
    subjects = subject_breakdown(db, student.id)

    # GÖREV-bazlı bugün/hafta (her madde 1 görev; deneme soruları test'e karışmaz)
    from app.services import gorev_stats
    _wk_start = today - timedelta(days=6)
    _opts = joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject)
    _wk_tasks = (
        db.query(Task).options(_opts)
        .filter(Task.student_id == student.id, Task.date >= _wk_start,
                Task.date <= today, Task.is_draft.is_(False))
        .all()
    )
    _gw = gorev_stats.summarize(_wk_tasks)
    _gt = gorev_stats.summarize([t for t in _wk_tasks if t.date == today])

    # 30 günlük TEST trend serileri — yalnız soru bankası (deneme test'e karışmaz)
    completed_series = daily_completed_series(db, student.id, today, 30, tests_only=True)
    planned_series = daily_planned_series(db, student.id, today, 30, tests_only=True)
    trend_days = sorted(completed_series.keys())
    trend = [
        {
            "date": d.isoformat(),
            "label": d.strftime("%d %b"),
            "completed": completed_series[d],
            "planned": planned_series.get(d, 0),
        }
        for d in trend_days
    ]

    # Öğretmenin veliye yolladığı notlar (en yeniden eskiye, son 90 gün)
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    notes_q = (
        db.query(TeacherNoteToParent)
        .options(joinedload(TeacherNoteToParent.teacher))
        .filter(
            TeacherNoteToParent.student_id == student.id,
            TeacherNoteToParent.created_at >= cutoff,
        )
        .order_by(TeacherNoteToParent.created_at.desc())
        .limit(20)
        .all()
    )
    teacher_notes = [
        {
            "id": n.id,
            "body": n.body,
            "teacher_name": n.teacher.full_name if n.teacher else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "delivered_at": n.delivered_at.isoformat() if n.delivered_at else None,
        }
        for n in notes_q
    ]

    # Projeksiyon — gizli detayları sızdırmadan sadece veli için anlamlı kısım.
    # Status mevcut teacher template'indeki türetme kuralıyla aynı (gap/remaining oranı).
    proj = snap.projection
    remaining_work = proj.total_tests - proj.completed
    if remaining_work <= 0:
        status_v = "green"
    elif proj.gap < 0:
        status_v = "red" if abs(proj.gap) > remaining_work * 0.2 else "amber"
    elif proj.gap < remaining_work * 0.1:
        status_v = "amber"
    else:
        status_v = "green"

    projection_view = {
        "total_tests": proj.total_tests,
        "completed_tests": proj.completed,
        "remaining_tests": remaining_work,
        "rate_per_day": round(proj.rate_per_day, 2) if proj.rate_per_day is not None else None,
        "days_left_to_exam": proj.days_left,
        "expected_completed_by_exam": proj.projected_completable,
        "gap": proj.gap,
        "status": status_v,
    }

    return {
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "grade_level": student.grade_level,
            "is_graduate": student.is_graduate,
            "display_grade_label": student.display_grade_label,
            "academic_year": student.academic_year.name if student.academic_year else None,
            "exam_date": student.effective_exam_date.isoformat() if student.effective_exam_date else None,
            "exam_label": student.effective_exam_label,
            "exam_target": student.effective_exam_target.lower() if student.effective_exam_target else "none",
        },
        "today": {
            "planned": snap.today.planned,
            "completed": snap.today.completed,
            "gorev_total": _gt.gorev_total,
            "gorev_done": _gt.gorev_done,
        },
        "week": {
            "planned": snap.week.planned,
            "completed": snap.week.completed,
            "rate": round(100 * snap.week.completed / snap.week.planned) if snap.week.planned > 0 else None,
            "gorev_total": _gw.gorev_total,
            "gorev_done": _gw.gorev_done,
            "gorev_rate": (
                round(100 * _gw.gorev_done / _gw.gorev_total)
                if _gw.gorev_total > 0 else None
            ),
            "test_planned": _gw.test_planned,
            "test_completed": _gw.test_completed,
        },
        # "Son 7 Gün Oran" = planlanan→tamamlanan oranı (hit_rate_7d, 0..1).
        # rate_7d test/gün HIZIDIR (yüzde değil); oran için hit_rate kullanılır.
        "rate_7d_pct": (
            min(100, round(snap.hit_rate_7d * 100))
            if snap.hit_rate_7d is not None else None
        ),
        "rate_30d_pct": round(snap.rate_30d * 100) if snap.rate_30d is not None else None,
        "consistency_7d_pct": round(snap.consistency_7d * 100) if snap.consistency_7d is not None else None,
        "warning_level": snap.worst_warning_level,
        "subjects": subjects,
        "trend": trend,
        "projection": projection_view,
        "teacher_notes": teacher_notes,
    }


def student_week(db: Session, parent: User, student_id: int, start: date) -> dict[str, Any]:
    """Belirtilen tarih başlangıçlı 7 günlük read-only program görünümü."""
    student = assert_parent_can_view(db, parent, student_id)

    days = [start + timedelta(days=i) for i in range(7)]
    end_inclusive = start + timedelta(days=6)

    # Tek query'de bu pencerenin tüm görevleri — book.subject ve section.topic dahil
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(
            Task.student_id == student.id,
            Task.date >= start,
            Task.date <= end_inclusive,
            Task.is_draft.is_(False),  # veli sadece yayınlanmış programı görür
        )
        .all()
    )

    by_day: dict[date, list[dict[str, Any]]] = {d: [] for d in days}
    for t in tasks:
        # `book_items` adı template-friendly (Jinja'da `items` dict method'u ile çakışır)
        book_items = []
        for it in t.book_items:
            book_items.append({
                "book_name": it.book.name if it.book else None,
                "subject_name": it.book.subject.name if it.book and it.book.subject else None,
                "subject_id": it.book.subject_id if it.book else None,
                "section_label": it.section.label if it.section else None,
                "topic_name": it.section.topic.name if it.section and it.section.topic else None,
                "planned_count": it.planned_count,
                "completed_count": it.completed_count,
            })
        by_day[t.date].append({
            "id": t.id,
            "title": t.title,
            "type": t.type.value if t.type else None,
            "status": t.status.value if t.status else None,
            "book_items": book_items,
        })

    # Her gün sıralama: tamamlanmış sona, sonra subject sırasına göre
    def task_sort_key(td: dict) -> tuple:
        completed = td["status"] == "completed"
        first_subj = td["book_items"][0]["subject_id"] if td["book_items"] else 9999
        return (completed, first_subj or 9999, td["id"])
    for d in days:
        by_day[d].sort(key=task_sort_key)

    # GÖREV-bazlı kırılım — Task nesnelerinden (deneme soruları test'e karışmaz)
    from app.services import gorev_stats
    obj_by_day: dict[date, list[Task]] = {d: [] for d in days}
    for t in tasks:
        obj_by_day[t.date].append(t)

    days_payload = []
    for d in days:
        day_tasks = by_day[d]
        planned = sum(
            sum(it["planned_count"] for it in t["book_items"]) for t in day_tasks
        )
        completed = sum(
            sum(it["completed_count"] for it in t["book_items"]) for t in day_tasks
        )
        _g = gorev_stats.summarize(obj_by_day[d])
        days_payload.append({
            "date": d.isoformat(),
            "weekday": d.weekday(),
            "tasks": day_tasks,
            "task_count": len(day_tasks),
            "planned_total": planned,
            "completed_total": completed,
            # GÖREV-bazlı (her madde 1 görev; deneme/test/etkinlik AYRI)
            "gorev_total": _g.gorev_total,
            "gorev_done": _g.gorev_done,
            "test_planned": _g.test_planned,
            "test_completed": _g.test_completed,
            "deneme_count": _g.cat_total["deneme"] + _g.cat_total["tam_deneme"],
            "etkinlik_count": _g.cat_total["etkinlik"],
        })

    return {
        "student": {
            "id": student.id,
            "full_name": student.full_name,
        },
        "start": start.isoformat(),
        "end": end_inclusive.isoformat(),
        "prev_start": (start - timedelta(days=7)).isoformat(),
        "next_start": (start + timedelta(days=7)).isoformat(),
        "days": days_payload,
    }


def list_recent_notifications(db: Session, parent: User, limit: int = 50) -> list[dict[str, Any]]:
    """Veliye gönderilmiş geçmiş bildirimler — Bildirimler sayfası için."""
    if parent.role != UserRole.PARENT:
        return []
    rows = (
        db.query(NotificationLog)
        .options(joinedload(NotificationLog.student))
        .filter(NotificationLog.parent_id == parent.id)
        .order_by(NotificationLog.queued_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "kind": n.kind.value if n.kind else None,
            "channel": n.channel.value if n.channel else None,
            "status": n.status.value if n.status else None,
            "subject": n.subject,
            "student_name": n.student.full_name if n.student else None,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "queued_at": n.queued_at.isoformat() if n.queued_at else None,
        }
        for n in rows
    ]
