"""Stage 14 — Light gamification: streak + puan + rozet.

**Streak** = öğrencinin üst üste tamamladığı gün sayısı (en az 1 task veya
1 pomodoro work session bittiyse o gün "aktif" sayılır). TR günü esas alınır.

**Puan** = derive edilir (DB'de saklanmıyor):
- Her tamamlanan Task: 10 puan
- Her bitmiş pomodoro WORK session: 5 puan
- Her review rating: 2 puan
- Her kazanılmış rozet: 25 puan

**Rozet kataloğu** kodda sabit. Her rozet için bir `evaluate()` fonksiyonu
çalışır; koşul karşılanmışsa StudentBadge satırı eklenir (idempotent unique
constraint sayesinde duplicate-safe).

API:
- `compute_streak(student_id) → int (gün)`
- `compute_points(student_id) → int`
- `evaluate_badges_for_student(student_id) → list[awarded_badges]`

`evaluate_badges_for_student` her task/review/pomodoro tamamlama sonrası
trigger edilir (idempotent: zaten kazanılmış rozet tekrar verilmez).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    PomodoroSession,
    ReviewLog,
    StudentBadge,
    Task,
    TaskStatus,
)
from app.models.focus import PomodoroKind
from app.services.study_dna import TR_OFFSET_HOURS


# ============================================================================
# Rozet kataloğu
# ============================================================================


@dataclass(frozen=True)
class Badge:
    kind: str
    title: str
    description: str
    emoji: str
    tier: str  # bronze / silver / gold


BADGES: dict[str, Badge] = {
    "first_step": Badge(
        kind="first_step",
        title="İlk Adım",
        description="İlk görevini tamamla",
        emoji="🌱",
        tier="bronze",
    ),
    "streak_3": Badge(
        kind="streak_3",
        title="Üç Günlük Seri",
        description="3 gün üst üste aktif kal",
        emoji="🔥",
        tier="bronze",
    ),
    "streak_7": Badge(
        kind="streak_7",
        title="Haftalık Seri",
        description="7 gün üst üste aktif kal",
        emoji="⚡",
        tier="silver",
    ),
    "streak_30": Badge(
        kind="streak_30",
        title="Otuz Günlük Maraton",
        description="30 gün üst üste aktif kal",
        emoji="🏆",
        tier="gold",
    ),
    "task_marathon": Badge(
        kind="task_marathon",
        title="Görev Maratonu",
        description="Bir günde 10 görev tamamla",
        emoji="🏃",
        tier="silver",
    ),
    "early_bird": Badge(
        kind="early_bird",
        title="Erken Kuş",
        description="Sabah 06:00-09:00 arası 5 odak seansı",
        emoji="🐦",
        tier="silver",
    ),
    "pomodoro_pro": Badge(
        kind="pomodoro_pro",
        title="Odak Ustası",
        description="50 pomodoro seansı tamamla",
        emoji="🍅",
        tier="silver",
    ),
    "weekend_warrior": Badge(
        kind="weekend_warrior",
        title="Hafta Sonu Savaşçısı",
        description="4 farklı hafta sonu günü aktif kal",
        emoji="🛡️",
        tier="silver",
    ),
    "review_master": Badge(
        kind="review_master",
        title="Tekrar Şampiyonu",
        description="100 tekrar değerlendirmesi yap (FSRS)",
        emoji="🧠",
        tier="gold",
    ),
    "century_club": Badge(
        kind="century_club",
        title="Yüzler Kulübü",
        description="100 görev tamamla",
        emoji="💯",
        tier="gold",
    ),
}


BADGE_POINTS = 25
POINTS_PER_TASK = 10
POINTS_PER_POMO = 5
POINTS_PER_REVIEW = 2


# ============================================================================
# Streak + puan
# ============================================================================


def _tr_today(now: datetime) -> date:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone(timedelta(hours=TR_OFFSET_HOURS)))).date()


def _active_dates(db: Session, student_id: int, since_days: int = 60) -> set[date]:
    """Son N günde 'aktif' olan TR günleri (en az 1 task tamamlandı veya 1
    pomodoro work bitmiş)."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=since_days)

    days: set[date] = set()
    # Task'lardan
    task_rows = (
        db.query(Task.date)
        .filter(
            Task.student_id == student_id,
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.PARTIAL]),
            Task.date >= start.date(),
        )
        .all()
    )
    for (d,) in task_rows:
        days.add(d)
    # Pomodoro'lardan — TR günü
    pomo_rows = (
        db.query(PomodoroSession.started_at)
        .filter(
            PomodoroSession.student_id == student_id,
            PomodoroSession.kind == PomodoroKind.WORK,
            PomodoroSession.ended_at.isnot(None),
            PomodoroSession.actual_minutes >= 5,
            PomodoroSession.started_at >= start,
        )
        .all()
    )
    for (started,) in pomo_rows:
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        tr_d = started.astimezone(
            timezone(timedelta(hours=TR_OFFSET_HOURS))
        ).date()
        days.add(tr_d)
    return days


def compute_streak(
    db: Session, *, student_id: int, now: datetime | None = None
) -> int:
    """Bugünden geriye sayılan aktif gün serisi."""
    if now is None:
        now = datetime.now(timezone.utc)
    today = _tr_today(now)
    active = _active_dates(db, student_id, since_days=60)
    if not active:
        return 0
    # Bugün aktifse bugünden, değilse dünden başla
    if today in active:
        cur = today
    elif (today - timedelta(days=1)) in active:
        cur = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cur in active:
        streak += 1
        cur -= timedelta(days=1)
    return streak


def longest_streak(
    db: Session, *, student_id: int, since_days: int = 60
) -> int:
    """En uzun aktif gün serisi (window içinde)."""
    active = _active_dates(db, student_id, since_days=since_days)
    if not active:
        return 0
    sorted_days = sorted(active)
    longest = 1
    cur = 1
    for i in range(1, len(sorted_days)):
        if sorted_days[i] - sorted_days[i - 1] == timedelta(days=1):
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    return longest


@dataclass
class PointBreakdown:
    tasks: int
    pomodoros: int
    reviews: int
    badges: int
    total: int


def compute_points(
    db: Session, *, student_id: int, now: datetime | None = None
) -> PointBreakdown:
    """Toplam puan = Task tamamlama × 10 + pomodoro work × 5 + review × 2 + rozet × 25."""
    task_n = (
        db.query(func.count(Task.id))
        .filter(
            Task.student_id == student_id,
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.PARTIAL]),
        )
        .scalar()
        or 0
    )
    pomo_n = (
        db.query(func.count(PomodoroSession.id))
        .filter(
            PomodoroSession.student_id == student_id,
            PomodoroSession.kind == PomodoroKind.WORK,
            PomodoroSession.ended_at.isnot(None),
            PomodoroSession.actual_minutes >= 5,
        )
        .scalar()
        or 0
    )
    review_n = (
        db.query(func.count(ReviewLog.id))
        .filter(ReviewLog.student_id == student_id)
        .scalar()
        or 0
    )
    badge_n = (
        db.query(func.count(StudentBadge.id))
        .filter(StudentBadge.student_id == student_id)
        .scalar()
        or 0
    )
    total = (
        task_n * POINTS_PER_TASK
        + pomo_n * POINTS_PER_POMO
        + review_n * POINTS_PER_REVIEW
        + badge_n * BADGE_POINTS
    )
    return PointBreakdown(
        tasks=task_n * POINTS_PER_TASK,
        pomodoros=pomo_n * POINTS_PER_POMO,
        reviews=review_n * POINTS_PER_REVIEW,
        badges=badge_n * BADGE_POINTS,
        total=int(total),
    )


# ============================================================================
# Rozet kazanma kontrolleri
# ============================================================================


def _completed_task_count(db: Session, student_id: int) -> int:
    return (
        db.query(func.count(Task.id))
        .filter(
            Task.student_id == student_id,
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.PARTIAL]),
        )
        .scalar()
        or 0
    )


def _task_marathon_check(db: Session, student_id: int) -> bool:
    """Herhangi bir günde 10+ task tamamlandı mı?"""
    row = (
        db.query(Task.date, func.count(Task.id).label("c"))
        .filter(
            Task.student_id == student_id,
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.PARTIAL]),
        )
        .group_by(Task.date)
        .having(func.count(Task.id) >= 10)
        .first()
    )
    return row is not None


def _early_bird_count(db: Session, student_id: int) -> int:
    """Sabah 06-09 (TR) arası pomodoro WORK sayısı."""
    sessions = (
        db.query(PomodoroSession.started_at)
        .filter(
            PomodoroSession.student_id == student_id,
            PomodoroSession.kind == PomodoroKind.WORK,
            PomodoroSession.ended_at.isnot(None),
            PomodoroSession.actual_minutes >= 5,
        )
        .all()
    )
    n = 0
    tz_tr = timezone(timedelta(hours=TR_OFFSET_HOURS))
    for (started,) in sessions:
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        hour = started.astimezone(tz_tr).hour
        if 6 <= hour < 9:
            n += 1
    return n


def _pomodoro_count(db: Session, student_id: int) -> int:
    return (
        db.query(func.count(PomodoroSession.id))
        .filter(
            PomodoroSession.student_id == student_id,
            PomodoroSession.kind == PomodoroKind.WORK,
            PomodoroSession.ended_at.isnot(None),
            PomodoroSession.actual_minutes >= 5,
        )
        .scalar()
        or 0
    )


def _weekend_distinct_count(db: Session, student_id: int) -> int:
    """Farklı hafta sonu günleri sayısı (aktif)."""
    active = _active_dates(db, student_id, since_days=120)
    return sum(1 for d in active if d.weekday() >= 5)


def _review_count(db: Session, student_id: int) -> int:
    return (
        db.query(func.count(ReviewLog.id))
        .filter(ReviewLog.student_id == student_id)
        .scalar()
        or 0
    )


# Her rozet için (evaluator_fn, optional notes_fn)
# evaluator: db, student_id → bool (kazanıldı mı)
BADGE_EVALUATORS: dict[str, Callable[[Session, int], tuple[bool, str | None]]] = {
    "first_step": lambda db, sid: (
        _completed_task_count(db, sid) >= 1,
        None,
    ),
    "century_club": lambda db, sid: (
        _completed_task_count(db, sid) >= 100,
        None,
    ),
    "task_marathon": lambda db, sid: (
        _task_marathon_check(db, sid),
        None,
    ),
    "streak_3": lambda db, sid: (
        longest_streak(db, student_id=sid) >= 3,
        f"longest_streak>=3",
    ),
    "streak_7": lambda db, sid: (
        longest_streak(db, student_id=sid) >= 7,
        f"longest_streak>=7",
    ),
    "streak_30": lambda db, sid: (
        longest_streak(db, student_id=sid) >= 30,
        f"longest_streak>=30",
    ),
    "early_bird": lambda db, sid: (
        _early_bird_count(db, sid) >= 5,
        None,
    ),
    "pomodoro_pro": lambda db, sid: (
        _pomodoro_count(db, sid) >= 50,
        None,
    ),
    "weekend_warrior": lambda db, sid: (
        _weekend_distinct_count(db, sid) >= 4,
        None,
    ),
    "review_master": lambda db, sid: (
        _review_count(db, sid) >= 100,
        None,
    ),
}


def evaluate_badges_for_student(
    db: Session, *, student_id: int, commit: bool = False
) -> list[Badge]:
    """Kazanılması gereken yeni rozetleri ekle. Mevcut rozetler atlanır.

    Eklemeyi flush eder. `commit=True` ise commit; aksi halde çağıran sorumlu.
    Döner: yeni kazanılan Badge listesi.
    """
    earned_kinds = {
        k for (k,) in db.query(StudentBadge.badge_kind).filter(
            StudentBadge.student_id == student_id
        ).all()
    }
    newly: list[Badge] = []
    for kind, evaluator in BADGE_EVALUATORS.items():
        if kind in earned_kinds:
            continue
        try:
            won, notes = evaluator(db, student_id)
        except Exception:
            won, notes = False, None
        if won:
            db.add(StudentBadge(
                student_id=student_id,
                badge_kind=kind,
                notes=notes,
            ))
            newly.append(BADGES[kind])
    if newly:
        db.flush()
        if commit:
            db.commit()
    return newly


def list_student_badges(
    db: Session, *, student_id: int
) -> list[tuple[Badge, StudentBadge]]:
    """Öğrencinin kazanmış olduğu rozetler (Badge meta + kayıt)."""
    rows = (
        db.query(StudentBadge)
        .filter(StudentBadge.student_id == student_id)
        .order_by(StudentBadge.earned_at.desc())
        .all()
    )
    out = []
    for r in rows:
        meta = BADGES.get(r.badge_kind)
        if meta is None:
            continue
        out.append((meta, r))
    return out
