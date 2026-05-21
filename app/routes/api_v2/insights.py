"""API v2 — AI İçgörü + Öneri + Diagnostics (Dalga 3 Paket 9).

Endpoint haritası (prefix `/teacher/insights`):
  GET    /overview                                       → FleetInsightsResponse
  GET    /students/{id}/diagnostics                      → StudentDiagnosticsResponse
  GET    /students/{id}/suggestions?date=YYYY-MM-DD      → StudentSuggestionsPanelResponse
  GET    /students/{id}/suggestions/ahead                → StudentSuggestionsAheadResponse
  POST   /students/{id}/suggestions/accept               → MutationResponse[SuggestionAcceptResult]
  POST   /students/{id}/suggestions/reject               → MutationResponse[SuggestionRejectResult]
  POST   /students/{id}/suggestions/accept-all           → MutationResponse[SuggestionAcceptAllResult]

Cross-tenant 404: tüm öğrenci uçları teacher_id eşleşmesi şartını sürdürür.
Servisler hiç değiştirilmez; sadece Jinja shape → JSON shape adaptasyonu yapılır.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    Book,
    BookSection,
    FeedbackAction,
    SuggestionFeedback,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.models.user import TRACK_LABELS
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.insights import (
    DiagnosticsPatternRow,
    DiagnosticsRejectRow,
    DiagnosticsStudentRef,
    DiagnosticsVolumeRow,
    FleetInsightsResponse,
    HealthBadge,
    StudentDiagnosticsResponse,
    StudentMaturityItem,
    StudentSuggestionsAheadResponse,
    StudentSuggestionsPanelResponse,
    SuggestionAcceptAllBody,
    SuggestionAcceptAllResult,
    SuggestionAcceptBody,
    SuggestionAcceptResult,
    SuggestionDayBundle,
    SuggestionItem,
    SuggestionRejectBody,
    SuggestionRejectResult,
    TopPatternItem,
    WeekBucketItem,
)
from app.services.ai_insights import (
    HEALTH_COLORS,
    HEALTH_LABELS,
    build_fleet_insights,
)
from app.services.suggestions import (
    MATURITY_MIN_FLOOR,
    MATURITY_WEEKS,
    REJECT_DECAY_DAYS,
    REJECT_SCORE_PENALTY,
    REJECT_STRONG_COUNT,
    build_student_model,
    confidence_label,
    maturity,
    maturity_label,
    record_rejection,
    suggest_for_date,
)
from app.services.task_service import ReservationError, reserve_item


router = APIRouter(prefix="/teacher/insights", tags=["v2-teacher-insights"])


DOW_LABELS = [
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
]


# =============================================================================
# Auth + tenant kapısı
# =============================================================================


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise _auth_error(
            "Bu uç nokta öğretmen hesabı bekler",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "code": code, "message": message},
    )


def _validation_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": "validation", "code": code, "message": message},
    )


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "conflict", "code": code, "message": message},
    )


def _get_student_or_404(db: Session, teacher_id: int, student_id: int) -> User:
    s = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == teacher_id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not s:
        raise _not_found("student_not_found", "Öğrenci bulunamadı.")
    return s


def _invalidate_for(teacher_id: int, student_id: int | None = None) -> list[str]:
    keys = [
        f"teacher:{teacher_id}:insights:overview",
        f"teacher:{teacher_id}:program",
    ]
    if student_id is not None:
        keys.extend([
            f"teacher:{teacher_id}:insights:student:{student_id}",
            f"teacher:{teacher_id}:students:{student_id}",
        ])
    return keys


# =============================================================================
# Yardımcılar — Suggestion / health shape adaptörleri
# =============================================================================


def _adapt_suggestion(s) -> SuggestionItem:
    return SuggestionItem(
        book_id=s.book_id,
        book_name=s.book_name,
        book_type=s.book_type,
        section_id=s.section_id,
        section_label=s.section_label,
        subject_id=s.subject_id,
        subject_name=s.subject_name,
        topic_name=s.topic_name,
        planned_count=s.planned_count,
        remaining=s.remaining,
        confidence=round(float(s.confidence), 3),
        confidence_label=confidence_label(s.confidence),
        score=round(float(s.score), 3),
        reasons=list(s.reasons or []),
    )


def _badge(group: str, key: str) -> HealthBadge:
    label = HEALTH_LABELS.get(group, {}).get(key, key)
    color = HEALTH_COLORS.get(key, "#94a3b8")
    return HealthBadge(key=key, label=label, color=color)


# =============================================================================
# GET /overview
# =============================================================================


@router.get("/overview", response_model=FleetInsightsResponse)
def overview(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> FleetInsightsResponse:
    today = date.today()
    insights = build_fleet_insights(db, user.id, today=today)
    return FleetInsightsResponse(
        teacher_id=insights.teacher_id,
        today=today,
        students=[
            StudentMaturityItem(
                student_id=r.student_id,
                full_name=r.full_name,
                weeks_observed=r.weeks_observed,
                days_observed=r.days_observed,
                maturity_value=round(r.maturity_value, 3),
                maturity_text=r.maturity_text,
                accepted_count=r.accepted_count,
                rejected_count=r.rejected_count,
                acceptance_rate=(round(r.acceptance_rate, 3) if r.acceptance_rate is not None else None),
            )
            for r in insights.students
        ],
        fleet_total_accepted=insights.fleet_total_accepted,
        fleet_total_rejected=insights.fleet_total_rejected,
        fleet_acceptance_rate=(
            round(insights.fleet_acceptance_rate, 3)
            if insights.fleet_acceptance_rate is not None else None
        ),
        avg_maturity=round(insights.avg_maturity, 3),
        students_with_data=insights.students_with_data,
        top_accepted=[
            TopPatternItem(
                book_id=t.book_id, book_name=t.book_name,
                section_id=t.section_id, section_label=t.section_label,
                subject_name=t.subject_name, count=t.count, students=t.students,
            )
            for t in insights.top_accepted
        ],
        top_rejected=[
            TopPatternItem(
                book_id=t.book_id, book_name=t.book_name,
                section_id=t.section_id, section_label=t.section_label,
                subject_name=t.subject_name, count=t.count, students=t.students,
            )
            for t in insights.top_rejected
        ],
        weekly_trend=[
            WeekBucketItem(start=b.start, accepted=b.accepted, rejected=b.rejected)
            for b in insights.weekly_trend
        ],
        last_activity_at=insights.last_activity_at,
        health_overall=_badge("overall", insights.health.get("overall", "no_data")),
        health_activity=_badge("activity", insights.health.get("activity", "never")),
    )


# =============================================================================
# GET /students/{id}/diagnostics
# =============================================================================


@router.get(
    "/students/{student_id}/diagnostics",
    response_model=StudentDiagnosticsResponse,
)
def student_diagnostics(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> StudentDiagnosticsResponse:
    student = _get_student_or_404(db, user.id, student_id)
    today = date.today()
    model = build_student_model(db, student.id, today=today)
    mat = maturity(model)

    section_ids = {sid for (_, _, sid) in model.pattern_counts.keys()}
    book_ids = {bid for (_, bid, _) in model.pattern_counts.keys()}

    sections_map = {}
    if section_ids:
        sections_map = {
            s.id: s for s in db.query(BookSection)
            .options(
                joinedload(BookSection.topic),
                joinedload(BookSection.book).joinedload(Book.subject),
            )
            .filter(BookSection.id.in_(section_ids))
            .all()
        }
    books_map = {}
    if book_ids:
        books_map = {
            b.id: b for b in db.query(Book).options(joinedload(Book.subject))
            .filter(Book.id.in_(book_ids))
            .all()
        }

    pattern_rows: list[DiagnosticsPatternRow] = []
    for (dow, book_id, section_id), freq in model.pattern_counts.items():
        sec = sections_map.get(section_id)
        bk = books_map.get(book_id)
        counts_list = model.typical_counts.get((dow, book_id, section_id), [])
        typical = int(round(median(counts_list))) if counts_list else 0
        pattern_rows.append(DiagnosticsPatternRow(
            dow=dow,
            dow_label=DOW_LABELS[dow] if 0 <= dow <= 6 else "(?)",
            book_id=book_id,
            book_name=bk.name if bk else f"#{book_id}",
            subject_name=bk.subject.name if bk and bk.subject else "—",
            section_id=section_id,
            section_label=sec.label if sec else f"#{section_id}",
            topic_name=sec.topic.name if sec and sec.topic else None,
            freq=freq,
            typical_count=typical,
            samples=list(counts_list),
        ))
    pattern_rows.sort(key=lambda r: (-r.freq, r.dow, r.subject_name))

    volume_rows = [
        DiagnosticsVolumeRow(
            dow=dow,
            dow_label=DOW_LABELS[dow],
            task_count=model.typical_items_per_day.get(dow, 0),
            subject_count=model.typical_subjects_per_day.get(dow, 0),
        )
        for dow in range(7)
    ]

    reject_rows: list[DiagnosticsRejectRow] = []
    for (dow, book_id, section_id), w in model.reject_weights.items():
        sec = sections_map.get(section_id)
        bk = books_map.get(book_id)
        if not bk:
            bk = db.query(Book).options(joinedload(Book.subject)).filter(Book.id == book_id).first()
        if not sec:
            sec = db.query(BookSection).options(
                joinedload(BookSection.topic)
            ).filter(BookSection.id == section_id).first()
        cnt = model.reject_counts.get((dow, book_id, section_id), 0)
        reject_rows.append(DiagnosticsRejectRow(
            dow_label=DOW_LABELS[dow] if dow is not None and 0 <= dow <= 6 else "(genel)",
            book_id=book_id,
            book_name=bk.name if bk else f"#{book_id}",
            subject_name=bk.subject.name if bk and bk.subject else "—",
            section_id=section_id,
            section_label=sec.label if sec else f"#{section_id}",
            weight=round(w, 3),
            count=cnt,
            blocked=cnt >= REJECT_STRONG_COUNT,
        ))
    reject_rows.sort(key=lambda r: (-r.weight, r.book_name))

    total_accepted_count = sum(
        f.count for f in db.query(SuggestionFeedback)
        .filter(
            SuggestionFeedback.student_id == student.id,
            SuggestionFeedback.action == FeedbackAction.ACCEPTED,
        ).all()
    )
    total_rejected_count = sum(
        f.count for f in db.query(SuggestionFeedback)
        .filter(
            SuggestionFeedback.student_id == student.id,
            SuggestionFeedback.action == FeedbackAction.REJECTED,
        ).all()
    )

    base_value = min(1.0, model.weeks_observed / MATURITY_WEEKS)
    floor_applied = base_value < MATURITY_MIN_FLOOR and model.days_observed > 0

    return StudentDiagnosticsResponse(
        student=DiagnosticsStudentRef(id=student.id, full_name=student.full_name),
        today=today,
        weeks_observed=model.weeks_observed,
        days_observed=model.days_observed,
        maturity_value=round(mat, 4),
        maturity_label=maturity_label(mat),
        maturity_pct=int(round(mat * 100)),
        maturity_base=round(base_value, 4),
        maturity_floor_applied=floor_applied,
        maturity_weeks_constant=MATURITY_WEEKS,
        maturity_min_floor=MATURITY_MIN_FLOOR,
        reject_decay_days=REJECT_DECAY_DAYS,
        reject_strong_count=REJECT_STRONG_COUNT,
        reject_score_penalty=REJECT_SCORE_PENALTY,
        pattern_rows=pattern_rows,
        volume_rows=volume_rows,
        reject_rows=reject_rows,
        total_accepted=total_accepted_count,
        total_rejected=total_rejected_count,
    )


# =============================================================================
# GET /students/{id}/suggestions?date=YYYY-MM-DD
# =============================================================================


@router.get(
    "/students/{student_id}/suggestions",
    response_model=StudentSuggestionsPanelResponse,
)
def student_suggestions_for_day(
    student_id: int,
    date_param: str = Query(..., alias="date"),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> StudentSuggestionsPanelResponse:
    student = _get_student_or_404(db, user.id, student_id)
    try:
        target = date.fromisoformat(date_param)
    except ValueError:
        raise _validation_error("invalid_date", "Tarih formatı geçersiz (YYYY-MM-DD).")

    existing = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id, Task.date == target)
        .all()
    )
    exclude = {
        (it.book_id, it.book_section_id) for t in existing for it in t.book_items
    }

    model = build_student_model(db, student_id)
    suggs = suggest_for_date(db, student_id, target, model=model, exclude_keys=exclude)
    mat = maturity(model)

    active_phase = None
    if student.academic_year:
        ph = student.academic_year.active_phase_on(target)
        active_phase = ph.name if ph else None

    track_required = student.requires_track
    track_missing = track_required and student.track is None
    track_label = TRACK_LABELS.get(student.track) if student.track else None

    return StudentSuggestionsPanelResponse(
        student_id=student_id,
        target_date=target,
        suggestions=[_adapt_suggestion(s) for s in suggs],
        maturity_value=round(mat, 3),
        maturity_label=maturity_label(mat),
        weeks_observed=model.weeks_observed,
        days_observed=model.days_observed,
        active_phase=active_phase,
        track_required=track_required,
        track_missing=track_missing,
        track_label=track_label,
    )


# =============================================================================
# GET /students/{id}/suggestions/ahead — diagnostic 7-gün önizlemesi
# =============================================================================


@router.get(
    "/students/{student_id}/suggestions/ahead",
    response_model=StudentSuggestionsAheadResponse,
)
def student_suggestions_ahead(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> StudentSuggestionsAheadResponse:
    student = _get_student_or_404(db, user.id, student_id)
    today = date.today()
    model = build_student_model(db, student.id, today=today)
    days: list[SuggestionDayBundle] = []
    for i in range(7):
        d = today + timedelta(days=i)
        sugs = suggest_for_date(db, student.id, d, model=model, today=today)
        days.append(SuggestionDayBundle(
            date=d,
            suggestions=[_adapt_suggestion(s) for s in sugs],
        ))
    return StudentSuggestionsAheadResponse(
        student_id=student.id, today=today, days=days,
    )


# =============================================================================
# POST accept / reject / accept-all
# =============================================================================


def _record_acceptance(
    db: Session,
    student_id: int,
    book_id: int,
    section_id: int,
    day_of_week: int,
) -> None:
    existing = (
        db.query(SuggestionFeedback)
        .filter(
            SuggestionFeedback.student_id == student_id,
            SuggestionFeedback.book_id == book_id,
            SuggestionFeedback.book_section_id == section_id,
            SuggestionFeedback.day_of_week == day_of_week,
            SuggestionFeedback.action == FeedbackAction.ACCEPTED,
        )
        .first()
    )
    if existing:
        existing.count += 1
        return
    db.add(SuggestionFeedback(
        student_id=student_id,
        book_id=book_id,
        book_section_id=section_id,
        day_of_week=day_of_week,
        action=FeedbackAction.ACCEPTED,
        count=1,
    ))


def _create_task_from_suggestion(
    db: Session,
    student_id: int,
    target_date: date,
    book_id: int,
    section_id: int,
    planned_count: int,
) -> Task:
    book = db.query(Book).filter(Book.id == book_id).first()
    section = db.query(BookSection).filter(BookSection.id == section_id).first()
    if not book or not section:
        raise _validation_error("invalid_book_section", "Kitap/bölüm geçersiz.")

    try:
        reserve_item(
            db,
            student_id=student_id,
            book_id=book_id,
            section_id=section_id,
            count=planned_count,
        )
    except ReservationError as e:
        raise _conflict("reservation_failed", str(e))

    unit_word = "deneme" if book.type.value in ("brans_denemesi", "genel_deneme") else "test"
    title = f"{book.name} — {section.label}: {planned_count} {unit_word}"

    max_order = (
        db.query(Task.order)
        .filter(Task.student_id == student_id, Task.date == target_date)
        .order_by(Task.order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 0

    today = date.today()
    is_draft_default = target_date > today
    task = Task(
        student_id=student_id,
        date=target_date,
        type=TaskType.TEST,
        title=title,
        status=TaskStatus.PENDING,
        order=next_order,
        is_draft=is_draft_default,
        published_at=None if is_draft_default else datetime.now(timezone.utc),
    )
    db.add(task)
    db.flush()
    db.add(TaskBookItem(
        task_id=task.id,
        book_id=book_id,
        book_section_id=section_id,
        planned_count=planned_count,
        completed_count=0,
    ))
    _record_acceptance(db, student_id, book_id, section_id, target_date.weekday())
    return task


@router.post(
    "/students/{student_id}/suggestions/accept",
    response_model=MutationResponse[SuggestionAcceptResult],
)
def accept_suggestion(
    student_id: int,
    body: SuggestionAcceptBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[SuggestionAcceptResult]:
    _get_student_or_404(db, user.id, student_id)
    if body.planned_count < 1:
        raise _validation_error("invalid_planned_count", "planned_count ≥ 1 olmalı.")
    try:
        task = _create_task_from_suggestion(
            db, student_id, body.date, body.book_id, body.section_id, body.planned_count,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    return MutationResponse[SuggestionAcceptResult](
        data=SuggestionAcceptResult(accepted=True, task_id=task.id, date=body.date),
        invalidate=_invalidate_for(user.id, student_id),
    )


@router.post(
    "/students/{student_id}/suggestions/reject",
    response_model=MutationResponse[SuggestionRejectResult],
)
def reject_suggestion(
    student_id: int,
    body: SuggestionRejectBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[SuggestionRejectResult]:
    _get_student_or_404(db, user.id, student_id)
    dow = body.date.weekday()
    record_rejection(db, student_id, body.book_id, body.section_id, dow)
    db.commit()
    return MutationResponse[SuggestionRejectResult](
        data=SuggestionRejectResult(rejected=True),
        invalidate=_invalidate_for(user.id, student_id),
    )


@router.post(
    "/students/{student_id}/suggestions/accept-all",
    response_model=MutationResponse[SuggestionAcceptAllResult],
)
def accept_all_suggestions(
    student_id: int,
    body: SuggestionAcceptAllBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[SuggestionAcceptAllResult]:
    _get_student_or_404(db, user.id, student_id)
    created = 0
    errors: list[str] = []
    for item in body.items:
        if item.planned_count < 1:
            errors.append(f"#{item.book_id}/{item.section_id}: planned_count ≥ 1 olmalı")
            continue
        try:
            savepoint = db.begin_nested()
            _create_task_from_suggestion(
                db, student_id, body.date,
                item.book_id, item.section_id, item.planned_count,
            )
            savepoint.commit()
            created += 1
        except HTTPException as e:
            try:
                savepoint.rollback()
            except Exception:
                pass
            msg = e.detail.get("message") if isinstance(e.detail, dict) else str(e.detail)
            errors.append(f"#{item.book_id}/{item.section_id}: {msg}")
            continue
    if created > 0:
        db.commit()
    else:
        db.rollback()
    return MutationResponse[SuggestionAcceptAllResult](
        data=SuggestionAcceptAllResult(created_count=created, errors=errors),
        invalidate=_invalidate_for(user.id, student_id),
    )
