"""Öneri/öğrenme motoru tanı sayfası — sayısal model içgörüleri."""
from datetime import date, timedelta
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import (
    Book,
    BookSection,
    FeedbackAction,
    SuggestionFeedback,
    User,
    UserRole,
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
    suggest_for_date,
)
from app.templating import templates


router = APIRouter(prefix="/teacher/students")

DOW_LABELS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


@router.get("/{student_id}/suggestions-diagnostics")
def suggestions_diagnostics(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")

    today = date.today()
    model = build_student_model(db, student.id, today=today)
    mat = maturity(model)

    # Pattern tablosu — kitap/section adlarıyla zenginleştir
    section_ids = {sid for (_, _, sid) in model.pattern_counts.keys()}
    book_ids = {bid for (_, bid, _) in model.pattern_counts.keys()}
    sections_map = {
        s.id: s for s in db.query(BookSection)
        .options(joinedload(BookSection.topic), joinedload(BookSection.book).joinedload(Book.subject))
        .filter(BookSection.id.in_(section_ids))
        .all()
    } if section_ids else {}
    books_map = {
        b.id: b for b in db.query(Book).options(joinedload(Book.subject))
        .filter(Book.id.in_(book_ids))
        .all()
    } if book_ids else {}

    pattern_rows = []
    for (dow, book_id, section_id), freq in model.pattern_counts.items():
        sec = sections_map.get(section_id)
        bk = books_map.get(book_id)
        counts_list = model.typical_counts.get((dow, book_id, section_id), [])
        typical = int(round(median(counts_list))) if counts_list else 0
        pattern_rows.append({
            "dow": dow,
            "dow_label": DOW_LABELS[dow],
            "book_name": bk.name if bk else f"#{book_id}",
            "subject_name": bk.subject.name if bk and bk.subject else "—",
            "section_label": sec.label if sec else f"#{section_id}",
            "topic_name": sec.topic.name if sec and sec.topic else None,
            "freq": freq,
            "typical_count": typical,
            "samples": list(counts_list),
        })
    pattern_rows.sort(key=lambda r: (-r["freq"], r["dow"], r["subject_name"]))

    # Tipik hacim per dow
    volume_rows = []
    for dow in range(7):
        volume_rows.append({
            "dow": dow,
            "dow_label": DOW_LABELS[dow],
            "items": model.typical_items_per_day.get(dow, 0),
            "subjects": model.typical_subjects_per_day.get(dow, 0),
        })

    # Ret sinyalleri
    reject_rows = []
    for (dow, book_id, section_id), w in model.reject_weights.items():
        sec = sections_map.get(section_id)
        bk = books_map.get(book_id)
        # bu key'ler için book/section_map'i daha geniş çek
        if not bk:
            bk = db.query(Book).options(joinedload(Book.subject)).filter(Book.id == book_id).first()
        if not sec:
            sec = db.query(BookSection).options(
                joinedload(BookSection.topic)
            ).filter(BookSection.id == section_id).first()
        cnt = model.reject_counts.get((dow, book_id, section_id), 0)
        reject_rows.append({
            "dow_label": DOW_LABELS[dow] if dow is not None else "(genel)",
            "book_name": bk.name if bk else f"#{book_id}",
            "subject_name": bk.subject.name if bk and bk.subject else "—",
            "section_label": sec.label if sec else f"#{section_id}",
            "weight": round(w, 3),
            "count": cnt,
            "blocked": cnt >= REJECT_STRONG_COUNT,
        })
    reject_rows.sort(key=lambda r: (-r["weight"], r["book_name"]))

    # Toplam kabul/red sayıları
    total_accepted = (
        db.query(SuggestionFeedback)
        .filter(
            SuggestionFeedback.student_id == student.id,
            SuggestionFeedback.action == FeedbackAction.ACCEPTED,
        )
        .all()
    )
    total_accepted_count = sum(f.count for f in total_accepted)
    total_rejected = (
        db.query(SuggestionFeedback)
        .filter(
            SuggestionFeedback.student_id == student.id,
            SuggestionFeedback.action == FeedbackAction.REJECTED,
        )
        .all()
    )
    total_rejected_count = sum(f.count for f in total_rejected)

    # Önümüzdeki 7 günün önerileri (skor parçaları için tekrar üret)
    days_ahead = [today + timedelta(days=i) for i in range(7)]
    suggestions_by_day = {}
    for d in days_ahead:
        sugs = suggest_for_date(db, student.id, d, model=model, today=today)
        suggestions_by_day[d] = [
            {
                "subject": s.subject_name,
                "book": s.book_name,
                "section": s.section_label,
                "planned_count": s.planned_count,
                "remaining": s.remaining,
                "score": round(s.score, 3),
                "confidence": round(s.confidence, 3),
                "confidence_label": confidence_label(s.confidence),
                "reasons": s.reasons,
            }
            for s in sugs
        ]

    # Maturity formül parçaları
    base_value = min(1.0, model.weeks_observed / MATURITY_WEEKS)
    floor_applied = base_value < MATURITY_MIN_FLOOR and model.days_observed > 0

    return templates.TemplateResponse(
        "teacher/suggestions_diagnostics.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "today": today,
            "model": model,
            "maturity_value": mat,
            "maturity_label": maturity_label(mat),
            "maturity_pct": int(round(mat * 100)),
            "maturity_base": round(base_value, 4),
            "maturity_floor_applied": floor_applied,
            "MATURITY_WEEKS": MATURITY_WEEKS,
            "MATURITY_MIN_FLOOR": MATURITY_MIN_FLOOR,
            "REJECT_DECAY_DAYS": REJECT_DECAY_DAYS,
            "REJECT_STRONG_COUNT": REJECT_STRONG_COUNT,
            "REJECT_SCORE_PENALTY": REJECT_SCORE_PENALTY,
            "pattern_rows": pattern_rows,
            "volume_rows": volume_rows,
            "reject_rows": reject_rows,
            "total_accepted": total_accepted_count,
            "total_rejected": total_rejected_count,
            "days_ahead": days_ahead,
            "suggestions_by_day": suggestions_by_day,
            "DOW_LABELS": DOW_LABELS,
        },
    )
