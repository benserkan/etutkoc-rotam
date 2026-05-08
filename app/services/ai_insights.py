"""AI/Öneri sistemi performans analitiği.

Öğretmenin öneri motorunun çalışıp çalışmadığını, ne öğrendiğini ve önerilerinin
ne kadarını kabul ettiğini görsel olarak takip etmesini sağlar.

Veri kaynakları:
- `suggestion_feedback` tablosu (ACCEPTED ve REJECTED kayıtları)
- `tasks` + `task_book_items` (genel planlama hacmi)
- `app.services.suggestions.build_student_model` (her öğrenci için olgunluk)

Hesaplanan metrikler:
- **Olgunluk haritası**: her öğrencinin maturity skoru (0-1)
- **Kabul/Red oranı**: filo bazında ve öğrenci bazında
- **Top patternler**: en çok kabul/red edilen (kitap, bölüm) çiftleri
- **Trend**: son 4 haftada haftalık kabul/red sayısı
- **Sağlık ışıkları**: model çalıştı mı, son aktivite zamanı, vs
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    FeedbackAction,
    SuggestionFeedback,
    User,
    UserRole,
)
from app.services.suggestions import build_student_model, maturity, maturity_label


@dataclass
class StudentMaturityRow:
    student_id: int
    full_name: str
    weeks_observed: int
    days_observed: int
    maturity_value: float
    maturity_text: str
    accepted_count: int
    rejected_count: int
    acceptance_rate: float | None  # None = yetersiz veri


@dataclass
class TopPattern:
    book_id: int
    book_name: str
    section_id: int
    section_label: str
    subject_name: str
    count: int
    students: int      # kaç farklı öğrenci için


@dataclass
class WeekBucket:
    start: date         # haftanın başlangıcı (Pazartesi)
    accepted: int
    rejected: int


@dataclass
class FleetInsights:
    teacher_id: int
    students: list[StudentMaturityRow]
    fleet_total_accepted: int
    fleet_total_rejected: int
    fleet_acceptance_rate: float | None
    avg_maturity: float
    students_with_data: int
    top_accepted: list[TopPattern]
    top_rejected: list[TopPattern]
    weekly_trend: list[WeekBucket]
    last_activity_at: datetime | None
    health: dict[str, str]   # status_key → human label


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_fleet_insights(db: Session, teacher_id: int, today: date | None = None) -> FleetInsights:
    if today is None:
        today = date.today()

    students = (
        db.query(User)
        .filter(User.teacher_id == teacher_id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    student_ids = [s.id for s in students]

    # Tüm geribildirimleri tek seferde getir
    fbs = (
        db.query(SuggestionFeedback)
        .options(
            joinedload(SuggestionFeedback.book).joinedload(Book.subject),
            joinedload(SuggestionFeedback.section),
        )
        .filter(SuggestionFeedback.student_id.in_(student_ids) if student_ids else False)
        .all()
    )

    # Öğrenci bazında toplamlar
    by_student_acc: dict[int, int] = defaultdict(int)
    by_student_rej: dict[int, int] = defaultdict(int)
    for f in fbs:
        if f.action == FeedbackAction.ACCEPTED:
            by_student_acc[f.student_id] += f.count
        elif f.action == FeedbackAction.REJECTED:
            by_student_rej[f.student_id] += f.count

    # Pattern toplamları (book+section bazında)
    pat_acc: dict[tuple[int, int], dict] = {}
    pat_rej: dict[tuple[int, int], dict] = {}
    for f in fbs:
        key = (f.book_id, f.book_section_id)
        target = pat_acc if f.action == FeedbackAction.ACCEPTED else pat_rej
        if key not in target:
            target[key] = {
                "count": 0,
                "students": set(),
                "book": f.book,
                "section": f.section,
            }
        target[key]["count"] += f.count
        target[key]["students"].add(f.student_id)

    def _to_top(d: dict, k: int = 5) -> list[TopPattern]:
        rows = []
        for (book_id, section_id), v in d.items():
            book = v["book"]
            section = v["section"]
            rows.append(TopPattern(
                book_id=book_id,
                book_name=book.name if book else "?",
                section_id=section_id,
                section_label=section.label if section else "?",
                subject_name=book.subject.name if book and book.subject else "?",
                count=v["count"],
                students=len(v["students"]),
            ))
        rows.sort(key=lambda r: -r.count)
        return rows[:k]

    top_accepted = _to_top(pat_acc, 5)
    top_rejected = _to_top(pat_rej, 5)

    # Haftalık trend (son 4 hafta + bu hafta = 5 hafta)
    week_buckets: list[WeekBucket] = []
    for w in range(4, -1, -1):
        start = _monday_of(today) - timedelta(days=7 * w)
        end = start + timedelta(days=6)
        acc = 0
        rej = 0
        for f in fbs:
            ts = f.updated_at or f.created_at
            try:
                ts_date = ts.date() if hasattr(ts, "date") else date.today()
            except Exception:
                ts_date = date.today()
            if start <= ts_date <= end:
                if f.action == FeedbackAction.ACCEPTED:
                    acc += f.count
                elif f.action == FeedbackAction.REJECTED:
                    rej += f.count
        week_buckets.append(WeekBucket(start=start, accepted=acc, rejected=rej))

    # Öğrenci olgunluk satırları
    rows: list[StudentMaturityRow] = []
    sum_mat = 0.0
    students_with_data_count = 0
    for s in students:
        m = build_student_model(db, s.id, today=today)
        mv = maturity(m)
        sum_mat += mv
        if m.days_observed > 0:
            students_with_data_count += 1
        acc = by_student_acc.get(s.id, 0)
        rej = by_student_rej.get(s.id, 0)
        rate: float | None = None
        if (acc + rej) > 0:
            rate = acc / (acc + rej)
        rows.append(StudentMaturityRow(
            student_id=s.id,
            full_name=s.full_name,
            weeks_observed=m.weeks_observed,
            days_observed=m.days_observed,
            maturity_value=mv,
            maturity_text=maturity_label(mv),
            accepted_count=acc,
            rejected_count=rej,
            acceptance_rate=rate,
        ))

    fleet_acc = sum(r.accepted_count for r in rows)
    fleet_rej = sum(r.rejected_count for r in rows)
    fleet_rate: float | None = None
    if (fleet_acc + fleet_rej) > 0:
        fleet_rate = fleet_acc / (fleet_acc + fleet_rej)

    avg_mat = (sum_mat / len(rows)) if rows else 0.0

    # Son aktivite
    last_at: datetime | None = None
    for f in fbs:
        ts = f.updated_at or f.created_at
        if ts and (last_at is None or ts > last_at):
            last_at = ts

    # Sağlık ışıkları
    health: dict[str, str] = {}
    if not students:
        health["overall"] = "no_students"
    elif students_with_data_count == 0:
        health["overall"] = "no_data"
    elif avg_mat < 0.15:
        health["overall"] = "warming_up"
    elif avg_mat < 0.4:
        health["overall"] = "early"
    elif avg_mat < 0.7:
        health["overall"] = "growing"
    else:
        health["overall"] = "mature"

    if last_at:
        days_since = (datetime.now(timezone.utc) - last_at.replace(tzinfo=timezone.utc) if last_at.tzinfo is None else datetime.now(timezone.utc) - last_at).days
        if days_since == 0:
            health["activity"] = "today"
        elif days_since <= 3:
            health["activity"] = "recent"
        elif days_since <= 14:
            health["activity"] = "stale"
        else:
            health["activity"] = "cold"
    else:
        health["activity"] = "never"

    return FleetInsights(
        teacher_id=teacher_id,
        students=rows,
        fleet_total_accepted=fleet_acc,
        fleet_total_rejected=fleet_rej,
        fleet_acceptance_rate=fleet_rate,
        avg_maturity=avg_mat,
        students_with_data=students_with_data_count,
        top_accepted=top_accepted,
        top_rejected=top_rejected,
        weekly_trend=week_buckets,
        last_activity_at=last_at,
        health=health,
    )


HEALTH_LABELS: dict[str, dict[str, str]] = {
    "overall": {
        "no_students": "Öğrenci yok",
        "no_data": "Veri toplanmadı",
        "warming_up": "Isınıyor",
        "early": "Erken aşama",
        "growing": "Gelişiyor",
        "mature": "Olgun",
    },
    "activity": {
        "never": "Hiç etkileşim yok",
        "today": "Bugün aktif",
        "recent": "Son 3 günde aktif",
        "stale": "1-2 hafta önce aktif",
        "cold": "2 haftadan eski",
    },
}

HEALTH_COLORS: dict[str, str] = {
    "no_students": "#94a3b8",
    "no_data": "#94a3b8",
    "warming_up": "#d97706",
    "early": "#d97706",
    "growing": "#0ea5e9",
    "mature": "#059669",
    "never": "#dc2626",
    "today": "#059669",
    "recent": "#0ea5e9",
    "stale": "#d97706",
    "cold": "#dc2626",
}
