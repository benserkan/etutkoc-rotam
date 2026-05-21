"""API v1 — Öğrenci endpoint'leri (JSON).

- GET  /student/today                   → bugünkü görevler + özet
- POST /student/tasks/{id}/complete     → tek-tıkla tamamla
- GET  /student/review                  → due review kartları
- POST /student/review/{id}             → rating (1-4) gönder
- GET  /student/focus                   → aktif pomodoro + bugünkü özet + streak
- POST /student/focus/start             → yeni pomodoro session başlat
- POST /student/focus/{id}/end          → session bitir
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    Book,
    BookSection,
    PomodoroSession,
    ReviewCard,
    StudentBook,
    Task,
    TaskBookItem,
    TaskStatus,
    Topic,
    User,
    UserRole,
)
from app.models.focus import PomodoroKind
from app.routes.api_v1.dependencies import get_current_api_user
from app.services.event_triggers import on_task_completed
from app.services.fsrs import RATING_LABELS_TR, VALID_RATINGS
from app.services.gamification import (
    compute_points,
    compute_streak,
    evaluate_badges_for_student,
)
from app.services.pomodoro import (
    end_session,
    recent_sessions,
    start_session,
    today_summary,
)
from app.services.review_scheduler import (
    cards_breakdown,
    get_card,
    get_due_cards,
    record_review,
)
from app.services.task_service import (
    ReservationError,
    complete_task as svc_complete_task,
)


router = APIRouter(prefix="/student", tags=["student"])


# ============================================================================
# Schemas
# ============================================================================


class TaskItemOut(BaseModel):
    id: int
    book_id: int | None
    book_title: str | None
    section_id: int | None
    section_title: str | None
    topic_name: str | None
    planned_count: int
    completed_count: int


class TaskOut(BaseModel):
    id: int
    date: str  # ISO yyyy-mm-dd
    status: str
    title: str | None
    order: int
    items: list[TaskItemOut]
    completed_at: str | None

    @classmethod
    def from_orm_task(cls, task: Task) -> "TaskOut":
        items = []
        for it in task.book_items:
            sec = it.section
            items.append(TaskItemOut(
                id=it.id,
                book_id=it.book_id,
                book_title=it.book.name if it.book else None,
                section_id=it.book_section_id,
                section_title=sec.label if sec else None,
                topic_name=sec.topic.name if (sec and sec.topic) else None,
                planned_count=it.planned_count,
                completed_count=it.completed_count,
            ))
        return cls(
            id=task.id,
            date=task.date.isoformat(),
            status=task.status.value,
            title=task.title,
            order=task.order,
            items=items,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
        )


class DaySummaryOut(BaseModel):
    date: str
    total_tasks: int
    total_items: int
    planned_count: int
    completed_count: int


class TodayOut(BaseModel):
    summary: DaySummaryOut
    tasks: list[TaskOut]


class ReviewCardOut(BaseModel):
    id: int
    topic_id: int
    topic_name: str | None
    subject_name: str | None
    state: int
    state_label: str
    due_at: str | None
    stability: float
    difficulty: float
    reps: int
    lapses: int


class ReviewBreakdownOut(BaseModel):
    new: int
    learning: int
    review: int
    relearning: int
    due_now: int
    total: int


class ReviewIndexOut(BaseModel):
    due_cards: list[ReviewCardOut]
    breakdown: ReviewBreakdownOut
    rating_labels: dict[int, str]


class RatingIn(BaseModel):
    rating: int


class ReviewResultOut(BaseModel):
    card_id: int
    new_state: int
    new_state_label: str
    next_due_at: str | None
    stability: float


class PomodoroSessionOut(BaseModel):
    id: int
    kind: str
    label: str | None
    planned_minutes: int
    actual_minutes: int | None
    started_at: str
    ended_at: str | None
    interrupted: bool


class FocusTodayOut(BaseModel):
    active_session: PomodoroSessionOut | None
    work_minutes_today: int
    sessions_today: int
    streak_days: int
    points: int
    recent_sessions: list[PomodoroSessionOut]


class FocusStartIn(BaseModel):
    planned_minutes: int = 25
    kind: str = "work"
    label: str = ""


class FocusEndIn(BaseModel):
    actual_minutes: int | None = None
    interrupted: bool = False


# ============================================================================
# Helpers
# ============================================================================


def _require_student(user: User) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Bu endpoint öğrencilere özeldir.", "code": "not_student"},
        )
    return user


def _load_day_tasks(db: Session, student_id: int, d: date) -> list[Task]:
    return (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(
            Task.student_id == student_id,
            Task.date == d,
            Task.is_draft.is_(False),
        )
        .order_by(Task.order, Task.id)
        .all()
    )


def _state_label(state: int) -> str:
    from app.models import REVIEW_STATE_LABELS_TR
    return REVIEW_STATE_LABELS_TR.get(state, str(state))


def _serialize_session(s: PomodoroSession) -> PomodoroSessionOut:
    return PomodoroSessionOut(
        id=s.id,
        kind=s.kind.value if hasattr(s.kind, "value") else str(s.kind),
        label=s.label or None,
        planned_minutes=s.planned_minutes,
        actual_minutes=s.actual_minutes,
        started_at=s.started_at.isoformat() if s.started_at else "",
        ended_at=s.ended_at.isoformat() if s.ended_at else None,
        interrupted=bool(s.interrupted),
    )


# ============================================================================
# TODAY
# ============================================================================


@router.get("/today", response_model=TodayOut)
def student_today(
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    _require_student(user)
    today = date.today()
    tasks = _load_day_tasks(db, user.id, today)

    total_items = sum(len(t.book_items) for t in tasks)
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)

    return TodayOut(
        summary=DaySummaryOut(
            date=today.isoformat(),
            total_tasks=len(tasks),
            total_items=total_items,
            planned_count=planned,
            completed_count=completed,
        ),
        tasks=[TaskOut.from_orm_task(t) for t in tasks],
    )


# ============================================================================
# TASK COMPLETE
# ============================================================================


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def student_task_complete(
    task_id: int,
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    _require_student(user)
    task = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(
            Task.id == task_id,
            Task.student_id == user.id,
            Task.is_draft.is_(False),
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"error": "Görev bulunamadı.", "code": "task_not_found"},
        )
    today = date.today()
    if task.date > today:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Bu görev {task.date.isoformat()} tarihli — henüz tamamlanamaz.",
                "code": "task_in_future",
            },
        )
    try:
        svc_complete_task(db, task)
    except ReservationError as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail={"error": str(e), "code": "reservation_error"}
        )
    try:
        on_task_completed(db, user)
    except Exception:
        pass
    try:
        evaluate_badges_for_student(db, student_id=user.id)
    except Exception:
        pass
    db.commit()
    db.refresh(task)
    return TaskOut.from_orm_task(task)


# ============================================================================
# REVIEW
# ============================================================================


@router.get("/review", response_model=ReviewIndexOut)
def student_review_index(
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    _require_student(user)
    now = datetime.now(timezone.utc)
    due = get_due_cards(db, student_id=user.id, now=now, limit=100)
    breakdown = cards_breakdown(db, student_id=user.id, now=now)

    cards_out = [
        ReviewCardOut(
            id=c.id,
            topic_id=c.topic_id,
            topic_name=c.topic.name if c.topic else None,
            subject_name=c.topic.subject.name if (c.topic and c.topic.subject) else None,
            state=c.state,
            state_label=_state_label(c.state),
            due_at=c.due_at.isoformat() if c.due_at else None,
            stability=float(c.stability or 0.0),
            difficulty=float(c.difficulty or 0.0),
            reps=c.reps or 0,
            lapses=c.lapses or 0,
        )
        for c in due
    ]
    return ReviewIndexOut(
        due_cards=cards_out,
        breakdown=ReviewBreakdownOut(
            new=breakdown.new,
            learning=breakdown.learning,
            review=breakdown.review,
            relearning=breakdown.relearning,
            due_now=breakdown.due_now,
            total=breakdown.total,
        ),
        rating_labels={int(k): v for k, v in RATING_LABELS_TR.items()},
    )


@router.post("/review/{card_id}", response_model=ReviewResultOut)
def student_review_rate(
    card_id: int,
    payload: RatingIn,
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    _require_student(user)
    if payload.rating not in VALID_RATINGS:
        raise HTTPException(
            status_code=400,
            detail={"error": "Geçersiz rating (1-4 olmalı).", "code": "bad_rating"},
        )
    card = get_card(db, card_id=card_id, student_id=user.id)
    if not card:
        raise HTTPException(
            status_code=404,
            detail={"error": "Kart bulunamadı.", "code": "card_not_found"},
        )
    now = datetime.now(timezone.utc)
    record_review(db, card=card, rating=payload.rating, now=now)
    try:
        evaluate_badges_for_student(db, student_id=user.id)
    except Exception:
        pass
    db.commit()
    db.refresh(card)
    return ReviewResultOut(
        card_id=card.id,
        new_state=card.state,
        new_state_label=_state_label(card.state),
        next_due_at=card.due_at.isoformat() if card.due_at else None,
        stability=float(card.stability or 0.0),
    )


# ============================================================================
# FOCUS / POMODORO
# ============================================================================


@router.get("/focus", response_model=FocusTodayOut)
def student_focus_today(
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    _require_student(user)
    now = datetime.now(timezone.utc)
    active = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.student_id == user.id,
            PomodoroSession.ended_at.is_(None),
        )
        .order_by(PomodoroSession.started_at.desc())
        .first()
    )
    summary = today_summary(db, student_id=user.id, now=now)
    recent = recent_sessions(db, student_id=user.id, limit=10)
    streak = compute_streak(db, student_id=user.id, now=now)
    points = compute_points(db, student_id=user.id)

    return FocusTodayOut(
        active_session=_serialize_session(active) if active else None,
        work_minutes_today=int(summary.work_minutes),
        sessions_today=int(summary.work_sessions),
        streak_days=int(streak),
        points=int(points.total),
        recent_sessions=[_serialize_session(s) for s in recent],
    )


@router.post("/focus/start", response_model=PomodoroSessionOut)
def student_focus_start(
    payload: FocusStartIn,
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    _require_student(user)
    try:
        pk = PomodoroKind(payload.kind)
    except ValueError:
        pk = PomodoroKind.WORK
    sess = start_session(
        db,
        student_id=user.id,
        planned_minutes=max(1, min(120, payload.planned_minutes)),
        kind=pk,
        label=payload.label or "",
    )
    db.commit()
    db.refresh(sess)
    return _serialize_session(sess)


@router.post("/focus/{session_id}/end", response_model=PomodoroSessionOut)
def student_focus_end(
    session_id: int,
    payload: FocusEndIn,
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    _require_student(user)
    sess = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.id == session_id,
            PomodoroSession.student_id == user.id,
        )
        .first()
    )
    if not sess:
        raise HTTPException(
            status_code=404,
            detail={"error": "Session bulunamadı.", "code": "session_not_found"},
        )
    end_session(
        db,
        session=sess,
        actual_minutes=payload.actual_minutes,
        interrupted=payload.interrupted,
    )
    try:
        evaluate_badges_for_student(db, student_id=user.id)
    except Exception:
        pass
    db.commit()
    db.refresh(sess)
    return _serialize_session(sess)
