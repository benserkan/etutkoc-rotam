"""INSTITUTION_ADMIN için agregasyon servisi.

Kurum yöneticisi öğretmenlerin DETAY verisini (program, notlar, tek tek
görev) GÖREMEZ — sadece toplu istatistikleri görür. Bu modül o agregasyonları
üretir.

Gizlilik prensipleri:
- Bir öğretmenin haftalık özetini hesaplarken sadece toplam/oran döner
- Öğrenci adları + sınıf görünür, detay sayfasına link YOK
- Kuruma ait olmayan öğretmen/öğrenci ASLA dönmemeli (caller institution_id geçer)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.services.analytics import week_stats_for, week_test_deneme_for


@dataclass
class TeacherSummary:
    teacher: User
    student_count: int
    planned: int          # bu hafta toplam planlanan TEST (soru bankası)
    completed: int        # bu hafta toplam tamamlanan TEST
    rate_pct: int | None  # 0-100 arası TEST tamamlama oranı (hiç plan yoksa None)
    last_login_days: int | None  # son giriş kaç gün önce (None = hiç)
    deneme_planned: int = 0    # bu hafta planlanan DENEME sorusu (branş/genel + tam)
    deneme_completed: int = 0  # bu hafta çözülen DENEME sorusu


def _days_since(dt: datetime | None, now: datetime) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(0, delta.days)


def teacher_summaries(
    db: Session, *, institution_id: int, today: date | None = None
) -> list[TeacherSummary]:
    """Bir kurumdaki tüm öğretmenler için haftalık agrega özet.

    Performans: N×M (her öğretmen için her öğrencisi için week_stats_for).
    Şu an küçük ölçek için yeterli; >100 öğretmen olunca tek SQL'e dönüştür.
    """
    if today is None:
        today = date.today()
    now = datetime.now(timezone.utc)

    teachers = (
        db.query(User)
        .filter(User.institution_id == institution_id, User.role == UserRole.TEACHER)
        .order_by(User.full_name)
        .all()
    )
    summaries: list[TeacherSummary] = []
    for t in teachers:
        students = (
            db.query(User)
            .filter(User.role == UserRole.STUDENT, User.teacher_id == t.id, User.is_active.is_(True))
            .all()
        )
        total_planned = 0
        total_completed = 0
        deneme_p = 0
        deneme_c = 0
        for s in students:
            td = week_test_deneme_for(db, s.id, today)  # test + deneme AYRI
            total_planned += td.test_planned
            total_completed += td.test_completed
            deneme_p += td.deneme_planned
            deneme_c += td.deneme_completed
        rate: int | None = None
        if total_planned > 0:
            rate = int(round(100 * total_completed / total_planned))
        summaries.append(TeacherSummary(
            teacher=t,
            student_count=len(students),
            planned=total_planned,
            completed=total_completed,
            rate_pct=rate,
            last_login_days=_days_since(t.last_login_at, now),
            deneme_planned=deneme_p,
            deneme_completed=deneme_c,
        ))
    return summaries


@dataclass
class InstitutionAggregate:
    teacher_count: int
    active_teacher_count: int  # son 7 günde login
    student_count: int
    total_planned: int
    total_completed: int
    weekly_rate_pct: int | None


def institution_aggregate(
    db: Session, *, institution_id: int, today: date | None = None
) -> InstitutionAggregate:
    """Kurum geneli haftalık özet — dashboard için."""
    summaries = teacher_summaries(db, institution_id=institution_id, today=today)
    teacher_count = len(summaries)
    active_teacher_count = sum(
        1 for s in summaries if s.last_login_days is not None and s.last_login_days <= 7
    )
    student_count = sum(s.student_count for s in summaries)
    total_planned = sum(s.planned for s in summaries)
    total_completed = sum(s.completed for s in summaries)
    rate: int | None = None
    if total_planned > 0:
        rate = int(round(100 * total_completed / total_planned))
    return InstitutionAggregate(
        teacher_count=teacher_count,
        active_teacher_count=active_teacher_count,
        student_count=student_count,
        total_planned=total_planned,
        total_completed=total_completed,
        weekly_rate_pct=rate,
    )


@dataclass
class StudentRosterRow:
    student: User
    teacher_name: str
    weekly_planned: int
    weekly_completed: int
    weekly_rate_pct: int | None


def institution_roster(
    db: Session, *, institution_id: int, today: date | None = None
) -> list[StudentRosterRow]:
    """Kurum altındaki tüm öğrenciler + öğretmenleri + haftalık özet.

    Filtreleme/sıralama route tarafında yapılır; bu helper sadece toplar.
    """
    if today is None:
        today = date.today()

    teachers = (
        db.query(User)
        .filter(User.institution_id == institution_id, User.role == UserRole.TEACHER)
        .all()
    )
    teacher_names = {t.id: t.full_name for t in teachers}
    teacher_ids = list(teacher_names.keys())

    if not teacher_ids:
        return []

    students = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.teacher_id.in_(teacher_ids),
        )
        .order_by(User.full_name)
        .all()
    )
    rows: list[StudentRosterRow] = []
    for s in students:
        w = week_stats_for(db, s.id, today)
        rate: int | None = None
        if w.planned > 0:
            rate = int(round(100 * w.completed / w.planned))
        rows.append(StudentRosterRow(
            student=s,
            teacher_name=teacher_names.get(s.teacher_id or 0, "—"),
            weekly_planned=w.planned,
            weekly_completed=w.completed,
            weekly_rate_pct=rate,
        ))
    return rows
