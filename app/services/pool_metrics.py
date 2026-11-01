"""Havuz öğrencisi için görev-bazlı OLMAYAN ölçüler (TEK MERKEZ).

Neden ayrı: havuzda görev yalnız öğrenci kaba aldığında doğar, yapılmayan kap gece silinir.
Görev sayan her yüzey (son 7 gün %, tutarlılık, tutturma, haftalık trend, görev uyumu) bu
yüzden yalnız YAPILANI görür ve %100'e yapışır (Taha #84: dönem %57 iken her yer %100).
Havuz öğrencisinde bu yüzeyler buradan beslenir:
  · havuz günü  = bir çalışma döneminin içindeki gün (her gün "programlı"dır)
  · aktif gün   = o gün herhangi bir görev işaretlendi
  · dönem birimi = pool_mode.period_summary (K42: test sayısı, etkinlik 1 birim)
Salt okuma; yazmaz.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import Task, User
from app.models.pool import PERIOD_BREAK, UNIT_ETKINLIK, PoolItem, StudyPeriod
from app.models.task import TaskStatus


def _periods(db: Session, student_id: int) -> list[StudyPeriod]:
    return (db.query(StudyPeriod).options(joinedload(StudyPeriod.items))
            .filter(StudyPeriod.student_id == student_id)
            .order_by(StudyPeriod.opened_on.asc(), StudyPeriod.id.asc()).all())


def period_ranges(db: Session, student_id: int, today: date,
                  periods: list[StudyPeriod] | None = None) -> list[tuple[StudyPeriod, date, date]]:
    """Her dönemin gün aralığı. Kural (weekly_progress ile aynı): kapanış günü yalnız o gün yeni
    dönem açıldıysa yeni döneme aittir; açık dönem beklenen seansın bir gün öncesine (ya da
    bugüne) kadar uzanır; sonraki dönemle çakışan kısım kırpılır."""
    periods = periods if periods is not None else _periods(db, student_id)
    out = []
    for i, p in enumerate(periods):
        nxt = periods[i + 1].opened_on if i + 1 < len(periods) else None
        if p.closed_on is not None:
            end = p.closed_on - timedelta(days=1) if nxt == p.closed_on else p.closed_on
        else:
            exp = (p.expected_next_on - timedelta(days=1)) if p.expected_next_on else p.opened_on
            end = max(exp, today)
        if nxt is not None and nxt <= end:
            end = nxt - timedelta(days=1)
        if end >= p.opened_on:
            out.append((p, p.opened_on, end))
    return out


def pool_days(db: Session, student_id: int, start: date, end: date, today: date,
              periods: list[StudyPeriod] | None = None) -> set[date]:
    """[start, end] içinde havuz dönemine düşen günler ('ara' tatili hariç)."""
    out: set[date] = set()
    for p, a, b in period_ranges(db, student_id, today, periods):
        if p.status == PERIOD_BREAK:
            continue
        d = max(a, start)
        while d <= min(b, end):
            out.add(d)
            d += timedelta(days=1)
    return out


def _task_done(t: Task) -> bool:
    return t.status == TaskStatus.COMPLETED or any((it.completed_count or 0) > 0 for it in t.book_items)


def active_days(db: Session, student_id: int, start: date, end: date) -> set[date]:
    tasks = (db.query(Task).options(joinedload(Task.book_items))
             .filter(Task.student_id == student_id, Task.is_draft.is_(False),
                     Task.date >= start, Task.date <= end).all())
    return {t.date for t in tasks if _task_done(t)}


def consistency(db: Session, student_id: int, today: date, days: int = 7) -> float | None:
    """Son N günün havuz günlerinden kaçında işaret var. Bugün yalnız işaret atıldıysa sayılır
    (gün sürüyor). Havuz günü yoksa None."""
    start = today - timedelta(days=days - 1)
    pdays = pool_days(db, student_id, start, today, today)
    act = active_days(db, student_id, start, today)
    if today in pdays and today not in act:
        pdays.discard(today)
    if not pdays:
        return None
    return len(act & pdays) / len(pdays)


def _cup_units_by_day(db: Session, period: StudyPeriod) -> dict[date, int]:
    """Öğrencinin kap görevlerinde işaretlediği birim, görev gününe göre (seans işareti tarihsizdir)."""
    items = {it.id: it for it in period.items if it.removed_at is None and it.counts_toward_pool}
    if not items:
        return {}
    tasks = (db.query(Task).options(joinedload(Task.book_items))
             .filter(Task.pool_item_id.in_(list(items))).all())
    out: dict[date, int] = defaultdict(int)
    for t in tasks:
        it = items.get(t.pool_item_id)
        if it is None:
            continue
        if it.unit == UNIT_ETKINLIK:
            out[t.date] += 1 if _task_done(t) else 0
        else:
            out[t.date] += sum(int(bi.completed_count or 0) for bi in t.book_items)
    return dict(out)


def period_units_upto(db: Session, period: StudyPeriod, upto: date | None, today: date) -> tuple[int, int]:
    """(yapılan, toplam) birim. upto None ya da dönem sonu → dönem özeti (seans işareti dahil);
    aksi halde öğrencinin upto gününe kadar işaretledikleri ("aynı noktaya kadar" kıyası)."""
    from app.services import pool_mode as pm
    sm = pm.period_summary(db, period, today)
    if upto is None:
        return sm.done_units, sm.total_units
    by_day = _cup_units_by_day(db, period)
    return min(sm.total_units, sum(u for d, u in by_day.items() if d <= upto)), sm.total_units


def subject_units(db: Session, period: StudyPeriod) -> dict[str, list[int]]:
    """Ders adı → [yapılan, toplam] birim (dönemin sayılan kalemleri)."""
    from app.services.pool_mode import _units
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for it in period.items:
        if it.removed_at is not None or not it.counts_toward_pool:
            continue
        t, d = _units(it)
        nm = it.subject.name if it.subject is not None else "Genel deneme"
        out[nm][0] += d
        out[nm][1] += t
    return dict(out)


def carry_counts(db: Session, period: StudyPeriod) -> tuple[int, int]:
    """(bu döneme devirle gelen kalem, bu dönemden sonrakine devreden kalem)."""
    from app.models.pool import SOURCE_CARRY
    live = [it for it in period.items if it.removed_at is None]
    came = sum(1 for it in live if it.source == SOURCE_CARRY)
    ids = [it.id for it in live]
    went = (db.query(PoolItem).filter(PoolItem.parent_item_id.in_(ids)).count() if ids else 0)
    return came, went


@dataclass
class PoolStatus:
    period_id: int
    status: str
    is_open: bool
    opened_on: date
    expected_next_on: date | None
    closed_on: date | None
    total_units: int
    done_units: int
    pct: int
    day_no: int            # açık dönemde bugün kaçıncı gün (1'den)
    days_planned: int      # açılış → beklenen seans (gün)
    pool_days_7: int       # son 7 gündeki havuz günü (bugün işaretsizse sayılmaz)
    active_days_7: int
    idle_streak: int       # dünden geriye işaretsiz havuz günü (bugün işaret varsa 0)
    last_active: date | None


def student_status(db: Session, student: User, today: date) -> PoolStatus | None:
    """Açık dönem (yoksa son dönem) + son 7 gün havuz katılımı. Dönem yoksa None."""
    from app.services import pool_mode as pm
    periods = _periods(db, student.id)
    if not periods:
        return None
    p = next((x for x in reversed(periods) if x.is_open), periods[-1])
    sm = pm.period_summary(db, p, today)
    start7 = today - timedelta(days=6)
    pd7 = pool_days(db, student.id, start7, today, today, periods)
    look = today - timedelta(days=60)
    act = active_days(db, student.id, look, today)
    if today in pd7 and today not in act:
        pd7.discard(today)
    streak = 0
    if today not in act:
        all_pd = pool_days(db, student.id, look, today - timedelta(days=1), today, periods)
        d = today - timedelta(days=1)
        while d in all_pd and d not in act:
            streak += 1
            d -= timedelta(days=1)
    planned = ((p.expected_next_on - p.opened_on).days if p.expected_next_on else 7) or 7
    return PoolStatus(
        period_id=p.id, status=p.status, is_open=p.is_open, opened_on=p.opened_on,
        expected_next_on=p.expected_next_on, closed_on=p.closed_on,
        total_units=sm.total_units, done_units=sm.done_units, pct=sm.pct,
        day_no=(today - p.opened_on).days + 1 if p.is_open else 0, days_planned=planned,
        pool_days_7=len(pd7), active_days_7=len(act & pd7), idle_streak=streak,
        last_active=max(act) if act else None,
    )
