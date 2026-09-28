"""Program Uyum Panosu servisi — kurum yöneticisi için (2026-05-20).

Çekirdek değer: öğretmenlerin hazırladığı programlara öğrenci uyumu.
Tamamlama = Σ completed_count ÷ Σ planned_count (yayınlanmış görevler).
Doğruluk = Σ correct ÷ (Σ correct + Σ wrong) — uyumun ötesinde kalite sinyali.

Veri yapısı `tenant_health._compute_weekly_completion_rate` deseniyle birebir
(Task + TaskBookItem + User.teacher_id); ek olarak taslak görevler hariç
(is_draft=False — öğrenciye gerçekten verilmiş program) + doğru/yanlış toplanır.

Gizlilik: kurum yöneticisi öğretmen/öğrenci ADINI + oranını görür, öğrenci
detay sayfası YOK (at-risk/burnout gizlilik deseni).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Book, Task, TaskBookItem, User, UserRole
from app.services import completion
from app.services.gorev_stats import DENEME_BOOK_TYPES

# Yeni öğrenci (hesap < bu gün) henüz programsızsa "boş program" sayılmaz —
# koça program kurması için onboarding penceresi (yanlış-pozitif önler).
EMPTY_PROGRAM_GRACE_DAYS = 3


# Tamamlama oranı renk eşikleri (D4 deseni)
def _rate_color(rate: int | None) -> str:
    if rate is None:
        return "slate"
    if rate >= 70:
        return "emerald"
    if rate >= 40:
        return "amber"
    return "rose"


def _accuracy(correct: int, wrong: int) -> int | None:
    total = correct + wrong
    if total <= 0:
        return None
    return int(round(100 * correct / total))


def _rate(planned: int, completed: int) -> int | None:
    if planned <= 0:
        return None
    return int(round(100 * completed / planned))


def _week_bounds(today: date, weeks_back: int = 0) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks_back)
    return monday, monday + timedelta(days=6)


def _student_totals_for_week(
    db: Session, *, student_ids: list[int], ws: date, we: date,
    today: date | None = None,
) -> dict[int, dict]:
    """Öğrenci başına planlı/çözülen test + doğru/yanlış — TEK TANIM
    (`app.services.completion`). `we` bugünden ilerideyse bugüne kesilir
    (vakti gelmemiş günlerin planı bölene girmesin)."""
    if today is None:
        today = date.today()
    effective_we = min(we, today)
    tot = completion.student_totals(db, student_ids, ws, effective_we)
    return {
        sid: {"planned": t.planned, "completed": t.completed,
              "correct": t.correct, "wrong": t.wrong}
        for sid, t in tot.items()
    }


def _summarize(totals: dict[int, dict]) -> dict:
    planned = sum(t["planned"] for t in totals.values())
    completed = sum(t["completed"] for t in totals.values())
    correct = sum(t["correct"] for t in totals.values())
    wrong = sum(t["wrong"] for t in totals.values())
    return {
        "planned": planned, "completed": completed,
        "correct": correct, "wrong": wrong,
        "rate": _rate(planned, completed),
        "accuracy": _accuracy(correct, wrong),
    }


def compute_compliance(db: Session, *, institution_id: int, weeks: int = 8) -> dict:
    """Program uyum panosu verisi — kurum özeti + trend + öğretmen/öğrenci kırılımı."""
    today = date.today()
    # Tamamlama: kayan 7 gün (TEK TANIM) — bu 7 gün vs önceki 7 gün
    this_ws, this_we = completion.window(today)
    last_ws, last_we = completion.window(today - timedelta(days=7))
    # "Programı var mı" ise takvim haftasına bakar (Pzt–Paz, ileri günler dahil)
    cal_ws, cal_we = _week_bounds(today, 0)

    # Aktif öğrenciler + koç eşlemesi
    students = (
        db.query(User.id, User.full_name, User.email, User.teacher_id, User.created_at)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        )
        .all()
    )
    student_ids = [int(s.id) for s in students]
    student_meta = {
        int(s.id): {"name": s.full_name or s.email, "teacher_id": s.teacher_id,
                    "created_at": s.created_at}
        for s in students
    }

    # Öğretmen adları
    teachers = (
        db.query(User.id, User.full_name, User.email)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id == institution_id,
        )
        .all()
    )
    teacher_name = {int(t.id): (t.full_name or t.email) for t in teachers}

    this_totals = _student_totals_for_week(db, student_ids=student_ids, ws=this_ws, we=this_we)
    last_totals = _student_totals_for_week(db, student_ids=student_ids, ws=last_ws, we=last_we)

    # "Programı var mı?" — takvim haftasının TAMAMI (gelecek günler dahil) ve
    # her görev türü. Eskiden bugüne kesilmiş TEST hacmine bakılıyordu → Pazartesi
    # günü, programı Salı'dan / Perşembe'den başlayan ya da yalnız etkinlik/deneme
    # görevi olan öğrenci "programsız" görünüyordu (2026-09-28 saha bulgusu).
    has_program: set[int] = set()
    if student_ids:
        has_program = {
            int(sid) for (sid,) in db.query(Task.student_id)
            .filter(Task.student_id.in_(student_ids), Task.is_draft.is_(False),
                    Task.date >= cal_ws, Task.date <= cal_we)
            .distinct()
            .all()
        }

    summary = _summarize(this_totals)
    last_summary = _summarize(last_totals)
    delta = None
    if summary["rate"] is not None and last_summary["rate"] is not None:
        delta = summary["rate"] - last_summary["rate"]

    # ---- Öğretmen kırılımı ----
    by_teacher: dict[int | None, dict] = {}
    for sid in student_ids:
        tid = student_meta[sid]["teacher_id"]
        b = by_teacher.setdefault(tid, {
            "planned": 0, "completed": 0, "correct": 0, "wrong": 0,
            "student_count": 0, "empty_students": 0,
            "last_planned": 0, "last_completed": 0,
            "last_correct": 0, "last_wrong": 0,
        })
        b["student_count"] += 1
        t = this_totals.get(sid)
        if sid not in has_program:
            b["empty_students"] += 1
        if t:
            b["planned"] += t["planned"]
            b["completed"] += t["completed"]
            b["correct"] += t["correct"]
            b["wrong"] += t["wrong"]
        lt = last_totals.get(sid)
        if lt:
            b["last_planned"] += lt["planned"]
            b["last_completed"] += lt["completed"]
            b["last_correct"] += lt["correct"]
            b["last_wrong"] += lt["wrong"]

    teacher_rows = []
    for tid, b in by_teacher.items():
        rate = _rate(b["planned"], b["completed"])
        teacher_rows.append({
            "teacher_id": tid,
            "teacher_name": teacher_name.get(tid, "Koçu atanmamış") if tid else "Koçu atanmamış",
            "student_count": b["student_count"],
            "empty_students": b["empty_students"],
            "planned": b["planned"],
            "completed": b["completed"],
            "rate": rate,
            "rate_color": _rate_color(rate),
            "accuracy": _accuracy(b["correct"], b["wrong"]),
            # Geçen takvim haftası (tam hafta) — hafta başında karar için
            "last_rate": _rate(b["last_planned"], b["last_completed"]),
            "last_accuracy": _accuracy(b["last_correct"], b["last_wrong"]),
            "last_planned": b["last_planned"],
        })
    # En düşük tamamlama üstte (dikkat); None (hiç plan) en sona
    teacher_rows.sort(key=lambda r: (r["rate"] is not None, r["rate"] if r["rate"] is not None else 999))

    # ---- Öğrenci dikkat listesi (planı olan + en düşük tamamlamalı) ----
    student_rows = []
    for sid, t in this_totals.items():
        if t["planned"] == 0:
            continue
        rate = _rate(t["planned"], t["completed"])
        tid = student_meta[sid]["teacher_id"]
        student_rows.append({
            "student_name": student_meta[sid]["name"],
            "teacher_name": teacher_name.get(tid, "—") if tid else "—",
            "planned": t["planned"],
            "completed": t["completed"],
            "rate": rate,
            "rate_color": _rate_color(rate),
            "accuracy": _accuracy(t["correct"], t["wrong"]),
        })
    student_rows.sort(key=lambda r: r["rate"] if r["rate"] is not None else 999)
    attention_students = student_rows[:25]

    # ---- Boş program: bu hafta hiç planlı görevi olmayan aktif öğrenci ----
    # Onboarding grace: yeni eklenen öğrenci (hesap < grace) henüz programsızsa
    # "boş" sayılmaz — koça program kurması için süre tanı (yanlış-pozitif önler).
    now = datetime.now(timezone.utc)
    empty_by_teacher: dict[int | None, dict] = {}
    empty_total = 0
    for sid in student_ids:
        if sid in has_program:
            continue
        created = student_meta[sid].get("created_at")
        if created is not None:
            c = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            if (now - c).days < EMPTY_PROGRAM_GRACE_DAYS:
                continue  # yeni öğrenci — onboarding penceresi
        empty_total += 1
        tid = student_meta[sid]["teacher_id"]
        e = empty_by_teacher.setdefault(tid, {"count": 0, "students": []})
        e["count"] += 1
        if len(e["students"]) < 10:
            e["students"].append(student_meta[sid]["name"])
    empty_rows = [
        {
            "teacher_id": tid,
            "teacher_name": teacher_name.get(tid, "Koçu atanmamış") if tid else "Koçu atanmamış",
            "count": e["count"],
            "sample_students": e["students"],
        }
        for tid, e in empty_by_teacher.items()
    ]
    empty_rows.sort(key=lambda r: -r["count"])

    # ---- Haftalık trend (son N hafta kurum tamamlama) ----
    trend = []
    for wb in range(weeks - 1, -1, -1):
        ws, we = completion.window(today - timedelta(days=7 * wb))
        wt = _student_totals_for_week(db, student_ids=student_ids, ws=ws, we=we)
        s = _summarize(wt)
        trend.append({
            "week_start": ws.isoformat(),
            "rate": s["rate"],
            "planned": s["planned"],
            "completed": s["completed"],
        })

    return {
        "summary": {
            "rate": summary["rate"],
            "rate_color": _rate_color(summary["rate"]),
            "last_week_rate": last_summary["rate"],
            "delta": delta,
            "planned": summary["planned"],
            "completed": summary["completed"],
            "accuracy": summary["accuracy"],
            "student_count": len(student_ids),
            "empty_count": empty_total,
            "week_start": this_ws.isoformat(),
            "week_end": this_we.isoformat(),
        },
        "trend": trend,
        "teachers": teacher_rows,
        "attention_students": attention_students,
        "empty_program": empty_rows,
    }
