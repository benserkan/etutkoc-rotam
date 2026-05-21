"""Stage 14 — Pomodoro odak servisleri.

- `start_session`: yeni PomodoroSession aç (started_at=now, ended_at=null)
- `end_session`: bitir (ended_at, actual_minutes, interrupted)
- `today_summary`: bugünkü toplam dakika, session sayısı, kind breakdown
- `recent_sessions`: son N session listele
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import PomodoroSession
from app.models.focus import PomodoroKind
from app.services.study_dna import TR_OFFSET_HOURS


MIN_PLANNED = 5
MAX_PLANNED = 120


def start_session(
    db: Session,
    *,
    student_id: int,
    planned_minutes: int = 25,
    kind: PomodoroKind = PomodoroKind.WORK,
    label: str | None = None,
    now: datetime | None = None,
) -> PomodoroSession:
    """Yeni pomodoro session başlat."""
    if planned_minutes < MIN_PLANNED:
        planned_minutes = MIN_PLANNED
    if planned_minutes > MAX_PLANNED:
        planned_minutes = MAX_PLANNED
    if now is None:
        now = datetime.now(timezone.utc)
    sess = PomodoroSession(
        student_id=student_id,
        kind=kind,
        planned_minutes=planned_minutes,
        actual_minutes=0,
        interrupted=False,
        started_at=now,
        label=(label or "").strip() or None,
    )
    db.add(sess)
    db.flush()
    return sess


def end_session(
    db: Session,
    *,
    session: PomodoroSession,
    actual_minutes: int | None = None,
    interrupted: bool = False,
    now: datetime | None = None,
) -> PomodoroSession:
    """Pomodoro session bitir."""
    if now is None:
        now = datetime.now(timezone.utc)
    if session.ended_at is not None:
        return session  # idempotent
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if actual_minutes is None:
        # Server-side hesapla: max(0, now - started_at) dakika
        actual_minutes = int(max(0, (now - started).total_seconds() / 60))
    actual_minutes = max(0, min(actual_minutes, MAX_PLANNED))
    session.ended_at = now
    session.actual_minutes = actual_minutes
    session.interrupted = bool(interrupted)
    db.flush()
    return session


@dataclass
class DaySummary:
    work_sessions: int
    work_minutes: int
    break_minutes: int
    total_minutes: int
    interrupted_count: int


def _today_tr(now: datetime) -> tuple[datetime, datetime]:
    """Bugünün TR günü için UTC başlangıç/bitiş."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    tr = now.astimezone(timezone(timedelta(hours=TR_OFFSET_HOURS)))
    start_tr = tr.replace(hour=0, minute=0, second=0, microsecond=0)
    end_tr = start_tr + timedelta(days=1)
    return start_tr.astimezone(timezone.utc), end_tr.astimezone(timezone.utc)


def today_summary(
    db: Session, *, student_id: int, now: datetime | None = None
) -> DaySummary:
    if now is None:
        now = datetime.now(timezone.utc)
    start_utc, end_utc = _today_tr(now)

    sessions = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.student_id == student_id,
            PomodoroSession.started_at >= start_utc,
            PomodoroSession.started_at < end_utc,
        )
        .all()
    )
    work_n = 0
    work_min = 0
    break_min = 0
    interrupted_n = 0
    for s in sessions:
        if s.kind == PomodoroKind.WORK:
            work_n += 1
            work_min += s.actual_minutes
            if s.interrupted:
                interrupted_n += 1
        else:
            break_min += s.actual_minutes
    return DaySummary(
        work_sessions=work_n,
        work_minutes=work_min,
        break_minutes=break_min,
        total_minutes=work_min + break_min,
        interrupted_count=interrupted_n,
    )


def recent_sessions(
    db: Session, *, student_id: int, limit: int = 20
) -> list[PomodoroSession]:
    return (
        db.query(PomodoroSession)
        .filter(PomodoroSession.student_id == student_id)
        .order_by(PomodoroSession.started_at.desc())
        .limit(limit)
        .all()
    )


def total_work_minutes(
    db: Session, *, student_id: int, since_days: int = 30, now: datetime | None = None
) -> int:
    """Son N gün toplam çalışma dakikası."""
    if now is None:
        now = datetime.now(timezone.utc)
    start = now - timedelta(days=since_days)
    val = (
        db.query(func.coalesce(func.sum(PomodoroSession.actual_minutes), 0))
        .filter(
            PomodoroSession.student_id == student_id,
            PomodoroSession.kind == PomodoroKind.WORK,
            PomodoroSession.started_at >= start,
        )
        .scalar()
    )
    return int(val or 0)


def auto_close_stale_sessions(
    db: Session,
    *,
    student_id: int | None = None,
    hours: int = 3,
    now: datetime | None = None,
) -> int:
    """Belirlenen süreden uzun süredir açık kalmış seansları otomatik kapat.

    Açık seans = `ended_at IS NULL`.
    Eski seans = `now - started_at > hours`.

    Kapatma kararı: öğrencinin kapatmayı unuttuğu varsayılır →
    `actual_minutes = planned_minutes`, `interrupted = True`.
    Bu sayede "açık unutulmuş" kayıtlar veri kalitesini bozmaz.

    Returns: kapatılan seans sayısı (commit çağıran sorumlu).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    q = db.query(PomodoroSession).filter(
        PomodoroSession.ended_at.is_(None),
        PomodoroSession.started_at < cutoff,
    )
    if student_id is not None:
        q = q.filter(PomodoroSession.student_id == student_id)
    stale = q.all()
    for sess in stale:
        # Planlanan süreyi gerçekleşmiş gibi say (üst sınır), kesintili olarak işaretle
        sess.ended_at = now
        sess.actual_minutes = min(sess.planned_minutes or 0, MAX_PLANNED)
        sess.interrupted = True
    if stale:
        db.flush()
    return len(stale)


def end_session_and_start_break(
    db: Session,
    *,
    session: PomodoroSession,
    actual_minutes: int | None = None,
    interrupted: bool = False,
    break_kind: PomodoroKind = PomodoroKind.SHORT_BREAK,
    break_minutes: int = 5,
    now: datetime | None = None,
) -> tuple[PomodoroSession, PomodoroSession]:
    """Mevcut seansı bitir + sıradaki molayı otomatik başlat.

    Atomik: tek transaction içinde end + start. Pomodoro klasiği
    (25 dk çalış + 5 dk mola) akışını "tek tıkla" oluşturmak için.

    Returns: (ended_session, new_break_session)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    ended = end_session(
        db, session=session, actual_minutes=actual_minutes,
        interrupted=interrupted, now=now,
    )
    new_break = start_session(
        db,
        student_id=session.student_id,
        planned_minutes=break_minutes,
        kind=break_kind,
        label=None,
        now=now,
    )
    return ended, new_break
