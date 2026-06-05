"""Veli Haftalık Rapor — doyurucu analiz (web + mobil paylaşır).

Bir velinin "çocuğum bu hafta nasıldı?" sorusuna tek ekranda yanıt:
  - bu hafta özeti (görev tamamlama % + çözülen test + çalışılan gün)
  - GEÇEN HAFTAYA KIYAS (düzeldi mi / düştü mü — manşet)
  - ders kırılımı (en çok çözülen / en çok aksatılan)
  - deneme performansı (son net + önceki aynı tür denemeye göre trend)
  - gün gün tamamlama (net etiketli — "%Z · X/Y görev · N test")
  - koç notları (son 14 gün)
  - sade-dil genel değerlendirme (verdict)

TEK KAYNAK: `gorev_stats.summarize` (görev/test/deneme ayrımı) + ExamResult.
Bu servis JSON-serializable dict döner; `WeeklyReportResponse` şemasıyla birebir.

GİZLİLİK (KVKK): veli görev tamamlama metriklerini + ders kırılımını + deneme
net/doğru/yanlış (paylaşım kararı 2026-06-01: varsayılan AÇIK) + veliye iletilmiş
koç notlarını görür. Konu bazında doğru/yanlış, öğrenci-öğretmen mesajları,
AI iç işleyiş PAYLAŞILMAZ.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    Task,
    TaskBookItem,
    TeacherNoteToParent,
    User,
)
from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection
from app.models.exam_result import ExamResult
from app.services import gorev_stats
from app.services.parent_view import ParentAccessDenied, assert_parent_can_view


# Pencere ayarları
EXAM_LOOKBACK_DAYS = 60      # "son denemeler" + net trend penceresi
EXAM_LIMIT = 8
NOTE_LOOKBACK_DAYS = 14      # koç notu penceresi


def _monday_of(d: date) -> date:
    """Verilen tarihin haftasının Pazartesi'si (0=Pzt)."""
    return d - timedelta(days=d.weekday())


def default_week_start(today: date | None = None) -> date:
    """Varsayılan hafta = en son TAMAMLANMIŞ hafta (geçen Pazartesi).

    Hafta ortasında açan veli, biten haftanın tam resmini görür (kıyas dürüst:
    tam hafta ↔ tam hafta). "Sonraki" ile bu haftaya (kısmi) geçilebilir.
    """
    today = today or date.today()
    return _monday_of(today) - timedelta(days=7)


def _section_label(section: Any) -> str:
    """ExamSection enum → TR etiket (LGS / TYT / AYT (...))."""
    if section is None:
        return "Deneme"
    if isinstance(section, ExamSection):
        return EXAM_SECTION_LABELS.get(section, section.value.upper())
    # str gelirse enum'a çevirmeyi dene
    try:
        return EXAM_SECTION_LABELS.get(ExamSection(section), str(section).upper())
    except (ValueError, KeyError):
        return str(section).upper()


def _section_value(section: Any) -> str | None:
    if section is None:
        return None
    return section.value if hasattr(section, "value") else str(section)


def _week_tasks(db: Session, student_id: int, start: date, end: date) -> list[Task]:
    """[start, end] aralığındaki yayınlanmış görevler (book+subject joinli)."""
    return (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
        )
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end,
            Task.is_draft.is_(False),
        )
        .all()
    )


def _verdict(level: str, direction: str, gorev_total: int) -> tuple[str, str]:
    """(verdict_level, verdict_text) — sade Türkçe, tek cümle."""
    if gorev_total == 0:
        return ("warn", "Bu hafta için yayınlanmış bir program görünmüyor. Koçunuzla iletişime geçebilirsiniz.")

    # level: "good" | "warn" | "bad"; direction: up | down | flat | none
    table: dict[tuple[str, str], str] = {
        ("good", "up"): "Harika bir hafta! Geçen haftaya göre belirgin bir yükseliş var.",
        ("good", "flat"): "İstikrarlı ve güçlü bir hafta — tempo korunuyor.",
        ("good", "down"): "Tamamlama yüksek; yine de geçen haftaya göre hafif bir düşüş var.",
        ("good", "none"): "Güçlü bir hafta — programın büyük kısmı tamamlandı.",
        ("warn", "up"): "Bu hafta geçen haftaya göre yükselişte; tempo artıyor.",
        ("warn", "flat"): "Geçen haftayla benzer bir tempo — biraz daha desteklenebilir.",
        ("warn", "down"): "Geçen haftaya göre bir düşüş var; bu haftaya dikkat etmekte fayda var.",
        ("warn", "none"): "Orta seviyede bir hafta — tamamlama biraz daha yükseltilebilir.",
        ("bad", "up"): "Geçen haftaya göre toparlanma başladı, ama tamamlama hâlâ düşük.",
        ("bad", "flat"): "Tamamlama düşük seyrediyor; koçla görüşmek faydalı olabilir.",
        ("bad", "down"): "Bu hafta düşüşte ve tamamlama düşük; koçunuzla iletişime geçmenizi öneririz.",
        ("bad", "none"): "Tamamlama bu hafta düşük; koçunuzla iletişime geçmenizi öneririz.",
    }
    return (level, table.get((level, direction), "Bu haftanın özeti aşağıda."))


def build_weekly_report(
    db: Session,
    parent: User,
    student_id: int,
    week_start: date | None = None,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Veliye doyurucu haftalık rapor verisi. `WeeklyReportResponse` ile birebir.

    Raises ParentAccessDenied if parent not linked (router 404'e çevirir).
    """
    student = assert_parent_can_view(db, parent, student_id)
    today = today or date.today()

    # Hafta sınırları — week_start daima Pazartesi'ye snap'lenir
    mon = _monday_of(week_start) if week_start else default_week_start(today)
    sun = mon + timedelta(days=6)
    last_mon = mon - timedelta(days=7)
    last_sun = mon - timedelta(days=1)

    # Bu hafta + geçen hafta görevlerini tek query'de çek
    all_tasks = _week_tasks(db, student.id, last_mon, sun)
    this_tasks = [t for t in all_tasks if mon <= t.date <= sun]
    last_tasks = [t for t in all_tasks if last_mon <= t.date <= last_sun]

    this_sum = gorev_stats.summarize(this_tasks)
    last_sum = gorev_stats.summarize(last_tasks)

    # --- Gün gün (bu hafta 7 gün) ---
    by_day: dict[date, list[Task]] = {mon + timedelta(days=i): [] for i in range(7)}
    for t in this_tasks:
        if t.date in by_day:
            by_day[t.date].append(t)

    daily: list[dict[str, Any]] = []
    active_days = 0
    for i in range(7):
        d = mon + timedelta(days=i)
        ds = gorev_stats.summarize(by_day[d])
        if ds.gorev_done > 0:
            active_days += 1
        daily.append({
            "date": d.isoformat(),
            "weekday": d.weekday(),
            "gorev_done": ds.gorev_done,
            "gorev_total": ds.gorev_total,
            "pct": ds.gorev_pct,
            "test_completed": ds.test_completed,
            "test_planned": ds.test_planned,
        })

    # --- Ders kırılımı (bu hafta, TEST görevleri) ---
    subjects: list[dict[str, Any]] = []
    most_completed_subject: str | None = None
    most_completed_val = -1
    most_neglected_subject: str | None = None
    most_neglected_pct: int | None = None
    for sg in this_sum.subjects:
        planned = sg.test_planned
        completed = sg.test_completed
        pct = round(100 * completed / planned) if planned > 0 else 0
        subjects.append({
            "subject_name": sg.subject_name,
            "planned": planned,
            "completed": completed,
            "pct": pct,
        })
        # En çok çözülen = hacimce en yüksek tamamlanan test
        if completed > most_completed_val:
            most_completed_val = completed
            most_completed_subject = sg.subject_name
        # En çok aksatılan = planlandı ama oranı en düşük (eksik iş var)
        if planned > 0 and pct < 100:
            if most_neglected_pct is None or pct < most_neglected_pct:
                most_neglected_pct = pct
                most_neglected_subject = sg.subject_name
    # completed=0 her yerde ise "en çok çözülen" anlamsız → gizle
    if most_completed_val <= 0:
        most_completed_subject = None
    # completed desc sırala (vitrin)
    subjects.sort(key=lambda s: (-s["completed"], -s["planned"]))

    # --- Geçen haftaya kıyas ---
    this_pct = this_sum.gorev_pct
    last_pct = last_sum.gorev_pct if last_sum.gorev_total > 0 else None
    completion_delta = (this_pct - last_pct) if last_pct is not None else None
    if completion_delta is None:
        direction = "none"
    elif completion_delta >= 5:
        direction = "up"
    elif completion_delta <= -5:
        direction = "down"
    else:
        direction = "flat"
    comparison = {
        "this_completion_pct": this_pct,
        "last_completion_pct": last_pct,
        "completion_delta": completion_delta,
        "this_test_completed": this_sum.test_completed,
        "last_test_completed": (last_sum.test_completed if last_sum.gorev_total > 0 else None),
        "test_delta": (
            this_sum.test_completed - last_sum.test_completed
            if last_sum.gorev_total > 0 else None
        ),
        "this_gorev_done": this_sum.gorev_done,
        "last_gorev_done": (last_sum.gorev_done if last_sum.gorev_total > 0 else None),
        "direction": direction,
    }

    # --- Deneme performansı (son 60 gün; net trendi aynı türe göre) ---
    exam_cutoff = today - timedelta(days=EXAM_LOOKBACK_DAYS)
    exam_rows = (
        db.query(ExamResult)
        .filter(
            ExamResult.student_id == student.id,
            ExamResult.exam_date >= exam_cutoff,
        )
        .order_by(ExamResult.exam_date.desc(), ExamResult.created_at.desc())
        .limit(EXAM_LIMIT)
        .all()
    )
    exams: list[dict[str, Any]] = []
    for r in exam_rows:
        exams.append({
            "title": r.title,
            "exam_date": r.exam_date.isoformat() if r.exam_date else None,
            "section_label": _section_label(r.section),
            "net": float(r.net) if r.net is not None else 0.0,
            "total_correct": int(r.total_correct or 0),
            "total_wrong": int(r.total_wrong or 0),
            "total_blank": int(r.total_blank or 0),
        })

    # Net trendi: en yeni denemenin türündeki bir önceki denemeyle kıyas
    exam_trend_delta: float | None = None
    exam_trend_section: str | None = None
    if exam_rows:
        latest = exam_rows[0]
        latest_section_val = _section_value(latest.section)
        prev_same = None
        for r in exam_rows[1:]:
            if _section_value(r.section) == latest_section_val:
                prev_same = r
                break
        if prev_same is not None and latest.net is not None and prev_same.net is not None:
            exam_trend_delta = round(float(latest.net) - float(prev_same.net), 2)
            exam_trend_section = _section_label(latest.section)

    # --- Koç notları (son 14 gün, veliye iletilmiş) ---
    note_cutoff = datetime.now(timezone.utc) - timedelta(days=NOTE_LOOKBACK_DAYS)
    note_rows = (
        db.query(TeacherNoteToParent)
        .options(joinedload(TeacherNoteToParent.teacher))
        .filter(
            TeacherNoteToParent.student_id == student.id,
            TeacherNoteToParent.created_at >= note_cutoff,
        )
        .order_by(TeacherNoteToParent.created_at.desc())
        .limit(10)
        .all()
    )
    teacher_notes = [
        {
            "body": n.body,
            "teacher_name": n.teacher.full_name if n.teacher else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in note_rows
    ]

    # --- Genel değerlendirme ---
    if this_pct >= 70:
        level = "good"
    elif this_pct >= 40:
        level = "warn"
    else:
        level = "bad"
    verdict_level, verdict_text = _verdict(level, direction, this_sum.gorev_total)

    return {
        "student": {"id": student.id, "full_name": student.full_name},
        "start": mon.isoformat(),
        "end": sun.isoformat(),
        "prev_start": last_mon.isoformat(),
        "next_start": (mon + timedelta(days=7)).isoformat(),
        "gorev_done": this_sum.gorev_done,
        "gorev_total": this_sum.gorev_total,
        "completion_pct": this_pct,
        "test_completed": this_sum.test_completed,
        "test_planned": this_sum.test_planned,
        "active_days": active_days,
        "daily": daily,
        "subjects": subjects,
        "most_completed_subject": most_completed_subject,
        "most_neglected_subject": most_neglected_subject,
        "most_neglected_pct": most_neglected_pct,
        "comparison": comparison,
        "exams": exams,
        "exam_trend_delta": exam_trend_delta,
        "exam_trend_section": exam_trend_section,
        "teacher_notes": teacher_notes,
        "verdict_level": verdict_level,
        "verdict_text": verdict_text,
    }
