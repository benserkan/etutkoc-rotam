from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
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
from app.services.suggestions import (
    build_student_model,
    confidence_label,
    maturity,
    maturity_label,
    record_rejection,
    suggest_for_date,
)
from app.services.task_service import ReservationError, reserve_item
from app.templating import templates


router = APIRouter(prefix="/teacher")


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
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    return s


@router.get("/students/{student_id}/suggestions-panel")
def suggestions_panel(
    student_id: int,
    request: Request,
    date_param: str = Query(..., alias="date"),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """HTMX fragment — belirli bir gün için öneri paneli."""
    _get_student_or_404(db, user.id, student_id)
    try:
        target = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(status_code=400)

    existing = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id, Task.date == target)
        .all()
    )
    exclude = {(it.book_id, it.book_section_id) for t in existing for it in t.book_items}

    model = build_student_model(db, student_id)
    suggs = suggest_for_date(db, student_id, target, model=model, exclude_keys=exclude)
    mat = maturity(model)

    # Aktif phase tespiti — UI'da ipucu için
    student = _get_student_or_404(db, user.id, student_id)
    active_phase = None
    if student.academic_year:
        active_phase = student.academic_year.active_phase_on(target)

    # Faz 7: Track durumu — 11+/mezun için zorunlu, eksikse uyarı banner
    from app.models.user import TRACK_LABELS
    track_required = student.requires_track
    track_missing = track_required and student.track is None
    track_label = TRACK_LABELS.get(student.track) if student.track else None

    return templates.TemplateResponse(
        "teacher/partials/suggestions_panel.html",
        {
            "request": request,
            "student_id": student_id,
            "target_date": target,
            "suggestions": suggs,
            "maturity_value": mat,
            "maturity_label": maturity_label(mat),
            "weeks_observed": model.weeks_observed,
            "days_observed": model.days_observed,
            "confidence_label": confidence_label,
            "active_phase": active_phase,
            "track_required": track_required,
            "track_missing": track_missing,
            "track_label": track_label,
        },
    )


def _record_acceptance(
    db: Session,
    student_id: int,
    book_id: int,
    section_id: int,
    day_of_week: int,
) -> None:
    """Kabul edilen öneriyi feedback tablosuna kaydeder (action=ACCEPTED).
    Aynı (öğrenci, kitap, bölüm, gün) için count'ı artırır.
    """
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
        raise HTTPException(status_code=400, detail="Kitap/bölüm geçersiz")

    try:
        reserve_item(
            db,
            student_id=student_id,
            book_id=book_id,
            section_id=section_id,
            count=planned_count,
        )
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    unit_word = "deneme" if book.type.value in ("brans_denemesi", "genel_deneme") else "test"
    title = f"{book.name} — {section.label}: {planned_count} {unit_word}"

    max_order = (
        db.query(Task.order)
        .filter(Task.student_id == student_id, Task.date == target_date)
        .order_by(Task.order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 0

    task = Task(
        student_id=student_id,
        date=target_date,
        type=TaskType.TEST,
        title=title,
        status=TaskStatus.PENDING,
        order=next_order,
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
    # AI insights için kabul olayını kaydet
    _record_acceptance(db, student_id, book_id, section_id, target_date.weekday())
    return task


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _render_day_card(request: Request, user: User, db: Session, student: User, day: date):
    """Swap sonrası day-card render — kart açık kalsın, sidebar yenilensin."""
    from app.routes.teacher_program import build_day_card_context
    ctx = build_day_card_context(db, student, day)
    response = templates.TemplateResponse(
        "teacher/partials/day_card.html",
        {"request": request, "user": user, "keep_open": "stay-open", **ctx},
    )
    response.headers["HX-Trigger"] = "tasks-changed"
    return response


@router.post("/students/{student_id}/suggestions/accept")
def accept_suggestion(
    student_id: int,
    request: Request,
    task_date: str = Form(..., alias="date"),
    book_id: int = Form(...),
    section_id: int = Form(...),
    planned_count: int = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = _get_student_or_404(db, user.id, student_id)
    try:
        target = date.fromisoformat(task_date)
    except ValueError:
        raise HTTPException(status_code=400)
    try:
        _create_task_from_suggestion(db, student_id, target, book_id, section_id, planned_count)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    if _is_htmx(request):
        return _render_day_card(request, user, db, student, target)
    return RedirectResponse(
        url=f"/teacher/students/{student_id}/week?start={target.isoformat()}",
        status_code=303,
    )


@router.post("/students/{student_id}/suggestions/reject")
def reject_suggestion(
    student_id: int,
    request: Request,
    task_date: str = Form(..., alias="date"),
    book_id: int = Form(...),
    section_id: int = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öneriyi reddet — o (öğrenci, kitap, bölüm, haftagünü) için negatif sinyal kaydet."""
    _get_student_or_404(db, user.id, student_id)
    try:
        target = date.fromisoformat(task_date)
    except ValueError:
        raise HTTPException(status_code=400)
    dow = target.weekday()
    record_rejection(db, student_id, book_id, section_id, dow)
    db.commit()
    # HTMX cevabı — sadece 204 (no content), istemci kartı kaldırır
    from fastapi import Response
    return Response(status_code=204)


@router.post("/students/{student_id}/suggestions/accept-all")
async def accept_all_suggestions(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Formdan gelen tüm seçili öneri satırlarını tek seferde oluştur."""
    student = _get_student_or_404(db, user.id, student_id)
    form = await request.form()
    date_str = form.get("date", "")
    try:
        target = date.fromisoformat(str(date_str))
    except ValueError:
        raise HTTPException(status_code=400)

    # Triplet formatı: book_id_<i>, section_id_<i>, planned_count_<i>
    # Basit yaklaşım: formdaki paralel listeler — getlist kullan
    book_ids = form.getlist("book_id")
    section_ids = form.getlist("section_id")
    counts = form.getlist("planned_count")

    if not (len(book_ids) == len(section_ids) == len(counts)):
        raise HTTPException(status_code=400, detail="Form alanları eşleşmiyor")

    created = 0
    errors: list[str] = []
    for raw_b, raw_s, raw_c in zip(book_ids, section_ids, counts):
        try:
            b = int(raw_b)
            s = int(raw_s)
            c = int(raw_c)
        except (TypeError, ValueError):
            continue
        if c < 1:
            continue
        try:
            _create_task_from_suggestion(db, student_id, target, b, s, c)
            db.flush()
            created += 1
        except HTTPException as e:
            errors.append(str(e.detail))
            db.rollback()
            continue
    db.commit()
    if _is_htmx(request):
        return _render_day_card(request, user, db, student, target)
    return RedirectResponse(
        url=f"/teacher/students/{student_id}/week?start={target.isoformat()}",
        status_code=303,
    )
