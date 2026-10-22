"""Program modu geçişi — gün gün ↔ haftalık havuz (2026-10-15, koç kuralı).

Geçiş iş akışının doğal sınırında yapılır:
  · GÜN GÜN → HAVUZ: program bittiğinde, yeni hafta başlamadan. Geçiş gününden (dahil) sonraki
    DOKUNULMAMIŞ görevler silinir ve kitap rezervleri iade edilir; kısmen çözülmüş görev KALIR (çözülen
    kısım müfredata/kitaba yazılmıştır), kalan rezervi serbest bırakılır. Geçmişte yapılmamış görevlerin
    ölü rezervleri de serbest bırakılır. İsteğe bağlı: aynı gün ilk havuz dönemi açılır.
  · HAVUZ → GÜN GÜN: "Seansı bitir" anında (ya da açık dönem yokken elle). Dönem kapanır, yeni dönem
    AÇILMAZ; kalan kalemler havuzdan çıkar (dönem geçmişinde iz olarak durur). Bugün ve sonrası için
    kaba alınmış ama dokunulmamış görevler silinir; kısmen çözülmüş kap görevi kalır.
Her geçiş `program_mode_changes` tablosuna yazılır. Aynı gün için iki mod birden olmaz.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Task, TaskBookItem, TaskStatus, User
from app.models.pool import (
    PERIOD_CLOSED, PROGRAM_MODE_GUN_GUN, PROGRAM_MODE_HAVUZ, ProgramModeChange, StudyPeriod,
)
from app.services import pool_mode as pm

TRIGGER_MANUAL = "manual"
TRIGGER_SESSION_FINISH = "session_finish"
# Gün güne geçtikten sonra koçun ilk programı yazması için tanınan süre ("programı yok" kırmızısı yerine sarı)
GUN_GUN_GRACE_DAYS = 3


class SwitchError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class TaskBrief:
    task_id: int
    date: str
    title: str
    planned: int
    completed: int
    is_draft: bool
    is_cup: bool


@dataclass
class SwitchPreview:
    from_mode: str
    to_mode: str
    effective_on: str
    allowed: bool
    blocker: str | None = None                  # open_period | same_mode
    blocker_message: str | None = None
    delete_tasks: list[TaskBrief] = field(default_factory=list)     # dokunulmamış → silinir
    keep_partial: list[TaskBrief] = field(default_factory=list)     # kısmen çözülmüş → kalır
    release_tests: int = 0                       # iade edilecek rezerv (silinen + kısmi kalan)
    dead_reserve_tests: int = 0                  # geçmişteki yapılmamış görevlerin ölü rezervi
    pool_leftover_items: int = 0                 # havuzdan çıkacak kalem (havuz → gün gün)
    pool_leftover_units: int = 0
    notes: list[str] = field(default_factory=list)


def _future_tasks(db: Session, student_id: int, effective_on: date) -> list[Task]:
    return (db.query(Task)
            .options(joinedload(Task.book_items))
            .filter(Task.student_id == student_id, Task.date >= effective_on,
                    Task.status != TaskStatus.COMPLETED)
            .order_by(Task.date, Task.id).all())


def _progress(t: Task) -> int:
    return sum(int(it.completed_count or 0) for it in t.book_items) + int(t.solved_count or 0)


def _brief(t: Task) -> TaskBrief:
    return TaskBrief(task_id=t.id, date=t.date.isoformat(), title=t.title or "—",
                     planned=sum(int(it.planned_count or 0) for it in t.book_items),
                     completed=sum(int(it.completed_count or 0) for it in t.book_items),
                     is_draft=bool(t.is_draft), is_cup=t.pool_item_id is not None)


def _live_reserve(t: Task) -> int:
    """Görevin hâlâ kilitli rezervi (kitaplı, serbest bırakılmamış, yapılmamış kısım)."""
    return sum(max(0, int(it.planned_count or 0) - int(it.completed_count or 0))
               for it in t.book_items
               if it.book_id is not None and it.reservation_released_at is None)


def _dead_reserve(db: Session, student_id: int, before: date) -> int:
    from app.services.task_service import dead_draft_clause

    rows = (db.query(TaskBookItem)
            .join(Task, Task.id == TaskBookItem.task_id)
            .filter(Task.student_id == student_id, Task.date < before,
                    Task.status != TaskStatus.COMPLETED, dead_draft_clause(before),
                    TaskBookItem.book_section_id.isnot(None),
                    TaskBookItem.reservation_released_at.is_(None)).all())
    return sum(max(0, int(r.planned_count or 0) - int(r.completed_count or 0)) for r in rows)


def preview(db: Session, student: User, to_mode: str, effective_on: date) -> SwitchPreview:
    cur = pm.mode_of(student)
    pv = SwitchPreview(from_mode=cur, to_mode=to_mode, effective_on=effective_on.isoformat(), allowed=True)
    if to_mode not in (PROGRAM_MODE_GUN_GUN, PROGRAM_MODE_HAVUZ):
        raise SwitchError("bad_mode", "Geçersiz program modu.")
    if cur == to_mode:
        pv.allowed, pv.blocker = False, "same_mode"
        pv.blocker_message = "Öğrenci zaten bu modda."
        return pv
    op = pm.get_open_period(db, student.id)
    if to_mode == PROGRAM_MODE_GUN_GUN and op is not None:
        pv.allowed, pv.blocker = False, "open_period"
        pv.blocker_message = ("Açık havuz dönemi var. Geçiş seansta yapılır: Seans ekranında “Seansı bitir” "
                              "penceresinde “Bu seansla gün gün programa geç” seçeneğini işaretle.")
    for t in _future_tasks(db, student.id, effective_on):
        if _progress(t) > 0:
            pv.keep_partial.append(_brief(t))
        else:
            pv.delete_tasks.append(_brief(t))
        pv.release_tests += _live_reserve(t)
    if to_mode == PROGRAM_MODE_HAVUZ:
        pv.dead_reserve_tests = _dead_reserve(db, student.id, effective_on)
        pv.notes.append("Çözülen testler müfredat haritasında ve kitap sayacında kalır; yalnız yapılmamış "
                        "kısımların rezervi iade edilir.")
        pv.notes.append("Haftalık program kayıtları ve iskelet silinmez; gün güne dönülürse yeniden kullanılır.")
    else:
        last = pm.latest_closed_period(db, student.id) if op is None else op
        if last is not None:
            left = [it for it in last.items if it.removed_at is None and it.remaining > 0 and it.counts_toward_pool]
            pv.pool_leftover_items = len(left)
            pv.pool_leftover_units = sum(int(it.remaining) for it in left)
        pv.notes.append("Kalan havuz kalemleri devredilmez; dönem geçmişinde iz olarak kalır. Gün gün programda "
                        "gerekiyorsa yeniden verilir.")
        pv.notes.append(f"İlk {GUN_GUN_GRACE_DAYS} gün “Programı yok” uyarısı kırmızı yerine sarı gösterilir "
                        "(ilk programı hazırlama süresi).")
    return pv


def _clean_future(db: Session, student: User, effective_on: date) -> dict:
    """Geçiş günü ve sonrası: dokunulmamış görevi sil (rezervi iade), kısmi görevin kalan rezervini bırak."""
    from app.services.task_service import release_item, release_task_items

    deleted = kept = released = 0
    now = datetime.now(timezone.utc)
    for t in _future_tasks(db, student.id, effective_on):
        released += _live_reserve(t)
        if _progress(t) > 0:
            for it in t.book_items:
                if it.book_id is None or it.reservation_released_at is not None:
                    continue
                rem = max(0, int(it.planned_count or 0) - int(it.completed_count or 0))
                if rem > 0:
                    release_item(db, student_id=student.id, book_id=it.book_id,
                                 section_id=it.book_section_id, count=rem)
                it.reservation_released_at = now
            kept += 1
            continue
        release_task_items(db, student.id, list(t.book_items))
        if t.carried_from_task_id is not None:
            src = db.get(Task, t.carried_from_task_id)
            if src is not None and src.carried_at is not None:
                src.carried_at = None
        if t.pool_item_id is not None:
            from app.services.pool_mode import detach_task_videos

            detach_task_videos(db, t.id)
        db.delete(t)
        deleted += 1
    db.flush()
    return {"deleted_tasks": deleted, "kept_partial_tasks": kept, "released_tests": released}


def _record(db: Session, *, student: User, from_mode: str, to_mode: str, effective_on: date,
            actor: User | None, trigger: str, period_id: int | None, note: str | None, summary: dict
            ) -> ProgramModeChange:
    ch = ProgramModeChange(student_id=student.id, from_mode=from_mode, to_mode=to_mode,
                           effective_on=effective_on, trigger=trigger,
                           changed_by_id=actor.id if actor else None, period_id=period_id,
                           note=(note or None), summary_json=json.dumps(summary, ensure_ascii=False))
    db.add(ch)
    db.flush()
    return ch


def switch_to_havuz(db: Session, *, student: User, actor: User | None, effective_on: date,
                    open_first_period: bool = True, expected_next_on: date | None = None,
                    note: str | None = None) -> ProgramModeChange:
    from app.services.task_service import reconcile_past_reservations

    if pm.mode_of(student) == PROGRAM_MODE_HAVUZ:
        raise SwitchError("same_mode", "Öğrenci zaten haftalık havuzda.")
    summary = _clean_future(db, student, effective_on)
    dead = reconcile_past_reservations(db, student_id=student.id, cutoff_date=effective_on)
    summary["dead_reserve_released"] = int(dead.get("released_tests", 0))
    pm.set_program_mode(db, student, PROGRAM_MODE_HAVUZ)
    period_id = None
    if open_first_period:
        p = pm.open_period(db, student=student, coach=actor, opened_on=effective_on,
                           expected_next_on=expected_next_on)
        period_id = p.id
    return _record(db, student=student, from_mode=PROGRAM_MODE_GUN_GUN, to_mode=PROGRAM_MODE_HAVUZ,
                   effective_on=effective_on, actor=actor, trigger=TRIGGER_MANUAL, period_id=period_id,
                   note=note, summary=summary)


def switch_to_gun_gun(db: Session, *, student: User, actor: User | None, effective_on: date,
                      trigger: str = TRIGGER_MANUAL, period_id: int | None = None,
                      note: str | None = None) -> ProgramModeChange:
    if pm.mode_of(student) == PROGRAM_MODE_GUN_GUN:
        raise SwitchError("same_mode", "Öğrenci zaten gün gün programda.")
    if pm.get_open_period(db, student.id) is not None:
        raise SwitchError("open_period", "Açık havuz dönemi var — önce seansı bitir (ya da dönemi kapat).")
    last = db.get(StudyPeriod, period_id) if period_id else pm.latest_closed_period(db, student.id)
    left = [it for it in (last.items if last else [])
            if it.removed_at is None and it.remaining > 0 and it.counts_toward_pool]
    summary = _clean_future(db, student, effective_on)
    summary["pool_leftover_items"] = len(left)
    summary["pool_leftover_units"] = sum(int(it.remaining) for it in left)
    pm.set_program_mode(db, student, PROGRAM_MODE_GUN_GUN)
    return _record(db, student=student, from_mode=PROGRAM_MODE_HAVUZ, to_mode=PROGRAM_MODE_GUN_GUN,
                   effective_on=effective_on, actor=actor, trigger=trigger,
                   period_id=(last.id if last else None), note=note, summary=summary)


def finish_session_to_gun_gun(db: Session, *, student: User, coach: User, period, closed_on: date,
                              record_session: bool, agenda: str | None, coach_note: str | None,
                              next_change: str | None, mood: int | None):
    """"Seansı bitir" + "Bu seansla gün gün programa geç": dönemi kapat → (isteğe bağlı) seans kaydı →
    yeni dönem AÇMA → mod gün gün. Tek işlem (çağıran commit eder)."""
    from app.models import CoachingSession
    from app.models.coaching_session import CoachingChannel, CoachingSessionStatus

    pm.close_period(db, period, closed_on=closed_on, status=PERIOD_CLOSED)
    session = None
    if record_session:
        session = CoachingSession(coach_id=coach.id, student_id=student.id, session_date=closed_on,
                                  status=CoachingSessionStatus.DONE, channel=CoachingChannel.IN_PERSON,
                                  agenda=(agenda or "Haftalık havuz değerlendirmesi — gün gün programa geçiş")[:5000],
                                  coach_note=(coach_note or None), next_change=(next_change or None), mood=mood)
        db.add(session)
        db.flush()
        period.closed_session_id = session.id
    ch = switch_to_gun_gun(db, student=student, actor=coach, effective_on=closed_on,
                           trigger=TRIGGER_SESSION_FINISH, period_id=period.id)
    return ch, session


def recent_switch_to_gun_gun(db: Session, student_id: int, today: date) -> ProgramModeChange | None:
    """Son GUN_GUN_GRACE_DAYS gün içinde gün güne geçiş var mı? (uyarı motoru için)"""
    ch = (db.query(ProgramModeChange)
          .filter(ProgramModeChange.student_id == student_id,
                  ProgramModeChange.to_mode == PROGRAM_MODE_GUN_GUN)
          .order_by(ProgramModeChange.effective_on.desc(), ProgramModeChange.id.desc()).first())
    if ch is None or (today - ch.effective_on).days >= GUN_GUN_GRACE_DAYS:
        return None
    return ch


def history(db: Session, student_id: int, limit: int = 20) -> list[ProgramModeChange]:
    return (db.query(ProgramModeChange).filter(ProgramModeChange.student_id == student_id)
            .order_by(ProgramModeChange.effective_on.desc(), ProgramModeChange.id.desc()).limit(limit).all())
