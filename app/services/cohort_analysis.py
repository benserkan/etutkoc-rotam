"""Kohort karşılaştırma — kurum içi gruplar için agrega istatistikler.

Bir kurumda öğrencileri farklı boyutlarda gruplayarak performansı kıyaslamak için:
- Sınıf seviyesi (5-12 + Mezun)
- Alan / Track (Sayısal/EA/Sözel/Dil) — sadece 11+/Mezun
- Müfredat modeli (LGS / Klasik Lise / Maarif Lise)
- Hedef sınav (LGS / YKS / Yıl Sonu)

Performans:
- Haftalık tamamlama oranı: tek SQL ile group by (no N+1)
- Risk yüzdesi: bulk_risk_assessment ile tek geçiş
- Week-over-week: 2 ayrı sorgu (bu hafta + geçen hafta)

Gizlilik:
- Bireysel öğrenci ID'si veya adı kohort sonucunda yok — sadece agrega
- Tenant izolasyonu: institution_id zorunlu

Tasarım kararları (2026-05-09):
- LEFT JOIN: hiç görevi olmayan öğrenciler de cohort'ta sayılır (planned=0)
- Sınıfı NULL olan öğrenciler "Sınıf belirsiz" kohortuna düşer
- Track gerektirmeyen öğrenciler (grade < 11) Alan kohortunda yok sayılır
- 0 öğrencili kohortlar return edilmez (UI'da boş kart göstermez)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import (
    CURRICULUM_MODEL_LABELS,
    CurriculumModel,
    EXAM_TARGET_LABELS,
    ExamTarget,
    Task,
    TaskBookItem,
    User,
    UserRole,
)
from app.models.user import GRADUATE_MODE_LABELS, TRACK_LABELS, GraduateMode, Track
from app.services.risk_analysis import bulk_risk_assessment, filter_at_risk


logger = logging.getLogger(__name__)


# ---------------------------- Veri yapıları ----------------------------


@dataclass
class CohortStats:
    cohort_key: str           # ör. "8", "sayisal", "lgs" — URL'de kullanılabilir
    cohort_label: str         # ör. "8. sınıf", "Sayısal alan"
    student_count: int        # cohort'taki aktif öğrenci sayısı
    weekly_planned: int       # son 7 gün planlanan toplam
    weekly_completed: int     # son 7 gün tamamlanan toplam
    weekly_rate_pct: int | None  # %completion — 0 plan ise None
    at_risk_count: int        # bu cohort'ta risk altında öğrenci sayısı
    at_risk_pct: int | None   # %risk — 0 öğrenci ise None
    # Renk kodu için kolaylık
    rate_color: str = field(default="slate")  # green / amber / red / slate (None için)


@dataclass
class WeekOverWeekDelta:
    """Bu hafta vs geçen hafta — kurum geneli."""
    this_week_rate: int | None
    last_week_rate: int | None
    delta_pct: int | None      # bu - geçen (pozitif iyi)
    direction: Literal["up", "down", "flat", "unknown"]


# ---------------------------- Yardımcılar ----------------------------


def _rate_color(pct: int | None) -> str:
    if pct is None:
        return "slate"
    if pct >= 70:
        return "green"
    if pct >= 40:
        return "amber"
    return "red"


def _week_range(today: date) -> tuple[date, date]:
    """Bu hafta için (start, end) — son 7 gün, end_inclusive=today."""
    return (today - timedelta(days=6), today)


def _grade_label(grade: int | None, is_graduate: bool = False) -> str:
    if is_graduate:
        return "🎓 Mezun"
    if grade is None:
        return "Sınıf belirsiz"
    return f"{grade}. sınıf"


# ---------------------------- Aggregate sorgusu ----------------------------


def _aggregate_completion_by_group(
    db: Session,
    *,
    institution_id: int,
    group_field,                # SQLAlchemy column expression for GROUP BY
    week_start: date,
    week_end: date,
    extra_filter=None,          # ek WHERE koşulu (örn. is_graduate=False)
) -> dict:
    """Tek SQL ile öğrenci sayısı + planned + completed sayılarını döner.

    Returns: dict[group_value, {"student_count", "planned", "completed"}]
    """
    # 1) Cohort'taki öğrenci sayısı (LEFT JOIN'siz, çünkü plan olmayan öğrenci de sayılır)
    student_q = (
        db.query(
            group_field.label("grp"),
            func.count(User.id).label("cnt"),
        )
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        )
        .group_by(group_field)
    )
    if extra_filter is not None:
        student_q = student_q.filter(extra_filter)
    student_counts = {row.grp: row.cnt for row in student_q.all()}

    # 2) Planned + completed: User → Task → TaskBookItem zinciri, group by cohort
    completion_q = (
        db.query(
            group_field.label("grp"),
            func.coalesce(func.sum(TaskBookItem.planned_count), 0).label("planned"),
            func.coalesce(func.sum(TaskBookItem.completed_count), 0).label("completed"),
        )
        .select_from(User)
        .join(Task, Task.student_id == User.id)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
            Task.date >= week_start,
            Task.date <= week_end,
        )
        .group_by(group_field)
    )
    if extra_filter is not None:
        completion_q = completion_q.filter(extra_filter)
    completion_data = {row.grp: (row.planned, row.completed) for row in completion_q.all()}

    # Birleştir: tüm cohort'lar (planı olmasa bile)
    result: dict = {}
    for grp, count in student_counts.items():
        planned, completed = completion_data.get(grp, (0, 0))
        result[grp] = {
            "student_count": count,
            "planned": int(planned),
            "completed": int(completed),
        }
    return result


def _make_cohort_stats(
    db: Session,
    *,
    cohort_key: str,
    cohort_label: str,
    student_ids: list[int],
    aggregate: dict,
    today: date,
) -> CohortStats:
    """Bir kohort için CohortStats üret — risk hesaplama dahil."""
    student_count = aggregate.get("student_count", 0)
    planned = aggregate.get("planned", 0)
    completed = aggregate.get("completed", 0)
    rate_pct: int | None = None
    if planned > 0:
        rate_pct = int(round(100 * completed / planned))

    # Risk yüzdesi: bu cohort'taki öğrencilerin risk durumu
    at_risk_count = 0
    at_risk_pct: int | None = None
    if student_ids:
        students = (
            db.query(User)
            .filter(User.id.in_(student_ids), User.is_active.is_(True))
            .all()
        )
        assessments = bulk_risk_assessment(db, students=students, today=today)
        at_risk = filter_at_risk(assessments, min_level="medium")
        at_risk_count = len(at_risk)
        if student_count > 0:
            at_risk_pct = int(round(100 * at_risk_count / student_count))

    return CohortStats(
        cohort_key=cohort_key,
        cohort_label=cohort_label,
        student_count=student_count,
        weekly_planned=planned,
        weekly_completed=completed,
        weekly_rate_pct=rate_pct,
        at_risk_count=at_risk_count,
        at_risk_pct=at_risk_pct,
        rate_color=_rate_color(rate_pct),
    )


def _student_ids_by_group(
    db: Session,
    *,
    institution_id: int,
    group_field,
    extra_filter=None,
) -> dict:
    """group_value → [student_id, ...] eşlemesi (risk hesaplama için)."""
    q = (
        db.query(group_field.label("grp"), User.id)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        )
    )
    if extra_filter is not None:
        q = q.filter(extra_filter)
    out: dict = {}
    for grp, uid in q.all():
        out.setdefault(grp, []).append(uid)
    return out


# ---------------------------- Cohort tipleri ----------------------------


def cohort_by_grade(
    db: Session, *, institution_id: int, today: date | None = None
) -> list[CohortStats]:
    """Sınıf seviyesi bazında karşılaştırma. Mezun ayrı kohort.

    Sıralama: 5, 6, 7, ..., 12, Mezun, Sınıf belirsiz (sona).
    """
    if today is None:
        today = date.today()
    week_start, week_end = _week_range(today)

    # is_graduate=True olanları "🎓 Mezun" olarak ayır; diğerlerini grade_level ile
    # SQLite case kullanımı için: is_graduate=True ise -1 (özel işaret)
    grade_expr = case(
        (User.is_graduate.is_(True), -1),
        else_=User.grade_level,
    )

    aggregates = _aggregate_completion_by_group(
        db,
        institution_id=institution_id,
        group_field=grade_expr,
        week_start=week_start,
        week_end=week_end,
    )
    student_ids_by_grp = _student_ids_by_group(
        db, institution_id=institution_id, group_field=grade_expr
    )

    out: list[CohortStats] = []
    # Sırala: 5, 6, ..., 12, sonra Mezun (-1), sonra NULL (sınıf belirsiz, 99)
    seen_keys = set(aggregates.keys()) | set(student_ids_by_grp.keys())
    sorted_keys = sorted(
        seen_keys,
        key=lambda k: (
            99 if k is None else  # NULL → en sona
            100 if k == -1 else   # mezun → 12'den hemen sonra ama NULL'dan önce
            int(k)                # normal grade
        ),
    )
    # Mezunu özel slot'a al — sona değil, 12'den sonra
    sorted_keys = (
        [k for k in sorted_keys if k not in (None, -1)] +
        ([-1] if -1 in sorted_keys else []) +
        ([None] if None in sorted_keys else [])
    )
    for key in sorted_keys:
        is_grad = (key == -1)
        grade_int = key if (key not in (None, -1)) else None
        label = _grade_label(grade_int, is_graduate=is_grad)
        cohort_key = "graduate" if is_grad else (str(grade_int) if grade_int else "unknown")
        sids = student_ids_by_grp.get(key, [])
        agg = aggregates.get(key, {"student_count": 0, "planned": 0, "completed": 0})
        # Aggregate dict student count'u group by'dan; emin olalım hizalı
        agg = dict(agg)
        agg["student_count"] = len(sids)
        if agg["student_count"] == 0:
            continue
        out.append(_make_cohort_stats(
            db, cohort_key=cohort_key, cohort_label=label,
            student_ids=sids, aggregate=agg, today=today,
        ))
    return out


def cohort_by_track(
    db: Session, *, institution_id: int, today: date | None = None
) -> list[CohortStats]:
    """Alan (Sayısal/EA/Sözel/Dil) bazında — sadece 11+ veya mezun öğrenciler.

    9-10. sınıf öğrencileri burada YOK (alan zorunlu değil).
    Track NULL olanlar "Alan seçilmemiş" kohortuna düşer (uyarı amaçlı).
    """
    if today is None:
        today = date.today()
    week_start, week_end = _week_range(today)

    extra = (
        (User.grade_level >= 11) | (User.is_graduate.is_(True))
    )
    aggregates = _aggregate_completion_by_group(
        db, institution_id=institution_id,
        group_field=User.track,
        week_start=week_start, week_end=week_end,
        extra_filter=extra,
    )
    student_ids_by_grp = _student_ids_by_group(
        db, institution_id=institution_id,
        group_field=User.track, extra_filter=extra,
    )

    out: list[CohortStats] = []
    track_order = [Track.SAYISAL, Track.EA, Track.SOZEL, Track.DIL, None]
    for tk in track_order:
        sids = student_ids_by_grp.get(tk, [])
        if not sids:
            continue
        label = TRACK_LABELS[tk] if tk else "⚠️ Alan seçilmemiş"
        cohort_key = tk.value if tk else "unset"
        agg = aggregates.get(tk, {"student_count": 0, "planned": 0, "completed": 0})
        agg = dict(agg)
        agg["student_count"] = len(sids)
        out.append(_make_cohort_stats(
            db, cohort_key=cohort_key, cohort_label=label,
            student_ids=sids, aggregate=agg, today=today,
        ))
    return out


def cohort_by_curriculum(
    db: Session, *, institution_id: int, today: date | None = None
) -> list[CohortStats]:
    """Müfredat modeli (LGS / Klasik Lise / Maarif Lise) karşılaştırması.

    NOT: effective_curriculum_model property; SQL group by için
    derive fonksiyonu var ama Python'da hesaplamak gerek (academic_year join + lojik).
    Tek seferlik tüm öğrenciler çekilip Python tarafında gruplanır.
    """
    if today is None:
        today = date.today()
    week_start, week_end = _week_range(today)

    # Tüm aktif öğrencileri çek
    students = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        )
        .all()
    )
    student_ids_by_curr: dict[CurriculumModel | None, list[int]] = {}
    for s in students:
        curr = s.effective_curriculum_model
        student_ids_by_curr.setdefault(curr, []).append(s.id)

    # Aggregates: her cohort için planned/completed
    out: list[CohortStats] = []
    curr_order = [
        CurriculumModel.LGS,
        CurriculumModel.KLASIK_LISE,
        CurriculumModel.MAARIF_LISE,
        None,
    ]
    for curr in curr_order:
        sids = student_ids_by_curr.get(curr, [])
        if not sids:
            continue
        # Bu cohort için planned/completed sum
        completion = (
            db.query(
                func.coalesce(func.sum(TaskBookItem.planned_count), 0).label("p"),
                func.coalesce(func.sum(TaskBookItem.completed_count), 0).label("c"),
            )
            .select_from(Task)
            .join(TaskBookItem, TaskBookItem.task_id == Task.id)
            .filter(
                Task.student_id.in_(sids),
                Task.date >= week_start,
                Task.date <= week_end,
            )
            .first()
        )
        planned, completed = (int(completion.p), int(completion.c)) if completion else (0, 0)
        label = CURRICULUM_MODEL_LABELS[curr] if curr else "Belirsiz müfredat"
        cohort_key = curr.value if curr else "unknown"
        agg = {"student_count": len(sids), "planned": planned, "completed": completed}
        out.append(_make_cohort_stats(
            db, cohort_key=cohort_key, cohort_label=label,
            student_ids=sids, aggregate=agg, today=today,
        ))
    return out


def cohort_by_exam_target(
    db: Session, *, institution_id: int, today: date | None = None
) -> list[CohortStats]:
    """Hedef sınav (LGS / YKS / Yıl Sonu) bazında karşılaştırma.

    effective_exam_target property tabanlı — Python'da hesaplanır.
    """
    if today is None:
        today = date.today()
    week_start, week_end = _week_range(today)

    students = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        )
        .all()
    )
    student_ids_by_target: dict[str, list[int]] = {}
    for s in students:
        # effective_exam_target "LGS"/"YKS"/None döndürür (uppercase string)
        tg_raw = s.effective_exam_target
        tg = tg_raw.lower() if tg_raw else "none"
        student_ids_by_target.setdefault(tg, []).append(s.id)

    out: list[CohortStats] = []
    target_order = ["lgs", "yks", "none"]
    for tg in target_order:
        sids = student_ids_by_target.get(tg, [])
        if not sids:
            continue
        completion = (
            db.query(
                func.coalesce(func.sum(TaskBookItem.planned_count), 0).label("p"),
                func.coalesce(func.sum(TaskBookItem.completed_count), 0).label("c"),
            )
            .select_from(Task)
            .join(TaskBookItem, TaskBookItem.task_id == Task.id)
            .filter(
                Task.student_id.in_(sids),
                Task.date >= week_start,
                Task.date <= week_end,
            )
            .first()
        )
        planned, completed = (int(completion.p), int(completion.c)) if completion else (0, 0)
        # Label
        try:
            label = EXAM_TARGET_LABELS[ExamTarget(tg)]
        except (ValueError, KeyError):
            label = "Belirsiz"
        agg = {"student_count": len(sids), "planned": planned, "completed": completed}
        out.append(_make_cohort_stats(
            db, cohort_key=tg, cohort_label=label,
            student_ids=sids, aggregate=agg, today=today,
        ))
    return out


# ---------------------------- Week-over-week ----------------------------


def institution_week_over_week(
    db: Session, *, institution_id: int, today: date | None = None
) -> WeekOverWeekDelta:
    """Bu hafta vs geçen hafta tamamlama oranı — kurum geneli."""
    if today is None:
        today = date.today()
    this_start, this_end = _week_range(today)
    last_end = today - timedelta(days=7)
    last_start, last_end = (last_end - timedelta(days=6), last_end)

    def _rate(start: date, end: date) -> int | None:
        row = (
            db.query(
                func.coalesce(func.sum(TaskBookItem.planned_count), 0).label("p"),
                func.coalesce(func.sum(TaskBookItem.completed_count), 0).label("c"),
            )
            .select_from(User)
            .join(Task, Task.student_id == User.id)
            .join(TaskBookItem, TaskBookItem.task_id == Task.id)
            .filter(
                User.role == UserRole.STUDENT,
                User.institution_id == institution_id,
                User.is_active.is_(True),
                Task.date >= start,
                Task.date <= end,
            )
            .first()
        )
        if not row or not row.p:
            return None
        return int(round(100 * row.c / row.p))

    this_rate = _rate(this_start, this_end)
    last_rate = _rate(last_start, last_end)

    delta: int | None = None
    direction: Literal["up", "down", "flat", "unknown"] = "unknown"
    if this_rate is not None and last_rate is not None:
        delta = this_rate - last_rate
        if delta > 2:
            direction = "up"
        elif delta < -2:
            direction = "down"
        else:
            direction = "flat"

    return WeekOverWeekDelta(
        this_week_rate=this_rate,
        last_week_rate=last_rate,
        delta_pct=delta,
        direction=direction,
    )
