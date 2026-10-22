"""Program geçmişi — gün gün haftalar + havuz dönemleri + mod geçişleri TEK zaman çizelgesi.

Neden: öğrenci havuza geçince hafta editörü kapanıyordu; geçmiş gün gün haftalarına hiçbir
yerden ulaşılamıyordu (Taha #84, 2026-10-22). Havuz "Dönem geçmişi" kartı da yalnız kapanmış
dönem varken çiziliyordu. Bu servis iki modun geçmişini aynı listede sunar.

Hafta sınırları `weekly_progress._weeks` ile AYNI kuraldan gelir (program haftası · takvim
haftası · havuz dönemi; geçişte yarıda kalan hafta `cut`). Sayılar `gorev_stats` tek merkezinden.
Salt okuma; AI/kredi yok.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session, selectinload

from app.models import Book, Task, TaskBookItem, User
from app.models.pool import PERIOD_STATUS_LABELS, PROGRAM_MODE_LABELS, ProgramModeChange, StudyPeriod
from app.services import gorev_stats, pool_mode as pm
from app.services.weekly_progress import _weeks

MAX_ENTRIES = 156  # ~3 yıl haftalık


@dataclass
class HistoryEntry:
    kind: str  # week | period | switch
    start: date
    end: date | None = None
    # hafta
    week_kind: str | None = None  # program | takvim
    program_id: int | None = None
    cut: bool = False
    gorev_total: int = 0
    gorev_done: int = 0
    test_planned: int = 0
    test_completed: int = 0
    deneme_units: int = 0
    deneme_done: int = 0
    pct: int = 0
    days_with_tasks: int = 0
    current: bool = False
    # dönem
    period: dict | None = None
    # geçiş
    switch: dict | None = None
    extra: dict = field(default_factory=dict)


def build_program_history(db: Session, student: User, *, today: date | None = None,
                          include_drafts: bool = False) -> list[HistoryEntry]:
    """Yeni → eski sıralı zaman çizelgesi. `include_drafts`: koç taslak görevleri de görür."""
    today = today or date.today()
    weeks = _weeks(db, student, today)
    out: list[HistoryEntry] = []

    gweeks = [w for w in weeks if w.kind != "donem" and w.start <= today]
    if gweeks:
        lo = min(w.start for w in gweeks)
        hi = max(w.end for w in gweeks)
        q = (db.query(Task)
             .options(selectinload(Task.book_items).selectinload(TaskBookItem.book).selectinload(Book.subject))
             .filter(Task.student_id == student.id, Task.date >= lo, Task.date <= hi))
        if not include_drafts:
            q = q.filter(Task.is_draft.is_(False))
        by_day: dict[date, list[Task]] = defaultdict(list)
        for t in q.all():
            by_day[t.date].append(t)
        for w in gweeks:
            ts = [t for d, lst in by_day.items() if w.start <= d <= w.end for t in lst]
            s = gorev_stats.summarize(ts)
            out.append(HistoryEntry(
                kind="week", start=w.start, end=w.end, week_kind=w.kind,
                program_id=w.program_id if w.program_id > 0 else None, cut=w.cut,
                gorev_total=s.gorev_total, gorev_done=s.gorev_done,
                test_planned=s.test_planned, test_completed=s.test_completed,
                deneme_units=s.deneme_units, deneme_done=s.deneme_units_done,
                pct=int(round(100 * gorev_stats.completion_pct(ts))),
                days_with_tasks=len({t.date for t in ts}),
                current=w.start <= today <= w.end,
            ))

    for p in (db.query(StudyPeriod).filter(StudyPeriod.student_id == student.id)
              .order_by(StudyPeriod.opened_on.asc()).all()):
        row = pm.history_row(db, p, today)
        row["status_label"] = PERIOD_STATUS_LABELS.get(p.status, p.status)
        out.append(HistoryEntry(kind="period", start=p.opened_on, end=p.closed_on, period=row,
                                current=p.closed_on is None))

    for c in (db.query(ProgramModeChange).filter(ProgramModeChange.student_id == student.id)
              .order_by(ProgramModeChange.effective_on.asc(), ProgramModeChange.id.asc()).all()):
        out.append(HistoryEntry(kind="switch", start=c.effective_on, switch={
            "from_mode": c.from_mode, "to_mode": c.to_mode,
            "from_label": PROGRAM_MODE_LABELS.get(c.from_mode, c.from_mode),
            "to_label": PROGRAM_MODE_LABELS.get(c.to_mode, c.to_mode),
            "note": c.note, "trigger": c.trigger,
        }))

    # Aynı günde: geçiş işareti, o gün başlayan dönem/haftanın ÜSTÜNDE dursun (yeni → eski).
    rank = {"switch": 0, "period": 1, "week": 2}
    out.sort(key=lambda e: (e.start, -rank[e.kind]), reverse=True)
    return out[:MAX_ENTRIES]
