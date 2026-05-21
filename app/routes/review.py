"""Stage 12 — Spaced repetition route'ları.

Öğrenci akışı:
- GET  /student/review                — bugünkü/gecikmiş kart listesi
- POST /student/review/{card_id}      — rating (1-4) gönder, FSRS güncelle

Öğretmen akışı:
- GET  /teacher/students/{id}/review        — öğrencinin kartlarını + ilerlemesini gör
- POST /teacher/students/{id}/review/seed   — Subject seçip topic'leri toplu seed

Yetki:
- Öğrenci yalnız kendi kartlarına erişir
- Öğretmen kendi öğrencilerine (teacher_id eşleşen)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
from urllib.parse import quote

from app.deps import get_current_user, get_db, require_teacher
from app.models import (
    REVIEW_STATE_LABELS_TR,
    REVIEW_STATE_NEW,
    ReviewCard,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services.fsrs import RATING_LABELS_TR, VALID_RATINGS
from app.services.review_scheduler import (
    cards_breakdown,
    get_card,
    get_due_cards,
    record_review,
    seed_subject_for_student,
    seed_topics_for_student,
    struggling_topics_for_student,
    teacher_review_load,
)
from app.templating import templates


router = APIRouter()


# ============================================================================
# ÖĞRENCİ
# ============================================================================


@router.get("/student/review")
def student_review_index(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Bu sayfa öğrencilere özeldir.")

    now = datetime.now(timezone.utc)
    due_cards = get_due_cards(db, student_id=user.id, now=now, limit=100)
    breakdown = cards_breakdown(db, student_id=user.id, now=now)

    flash_ok = request.query_params.get("ok")
    return templates.TemplateResponse(
        "student/review.html",
        {
            "request": request,
            "user": user,
            "due_cards": due_cards,
            "breakdown": breakdown,
            "rating_labels": RATING_LABELS_TR,
            "state_labels": REVIEW_STATE_LABELS_TR,
            "flash_ok": flash_ok,
        },
    )


@router.post("/student/review/{card_id}")
def student_review_rate(
    card_id: int,
    rating: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None or user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)
    if rating not in VALID_RATINGS:
        raise HTTPException(status_code=400, detail="Geçersiz rating (1-4 olmalı).")
    card = get_card(db, card_id=card_id, student_id=user.id)
    if not card:
        raise HTTPException(status_code=404, detail="Kart bulunamadı.")
    now = datetime.now(timezone.utc)
    record_review(db, card=card, rating=rating, now=now)
    # Stage 14: rozet kontrolü
    try:
        from app.services.gamification import evaluate_badges_for_student
        evaluate_badges_for_student(db, student_id=user.id)
    except Exception:
        pass
    db.commit()
    return RedirectResponse(url="/student/review", status_code=303)


# ============================================================================
# ÖĞRETMEN
# ============================================================================


@router.get("/teacher/students/{student_id}/review")
def teacher_student_review(
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
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı.")

    now = datetime.now(timezone.utc)
    breakdown = cards_breakdown(db, student_id=student.id, now=now)
    # Kartlar topic + subject ile listelensin
    cards = (
        db.query(ReviewCard)
        .options(joinedload(ReviewCard.topic).joinedload(Topic.subject))
        .filter(ReviewCard.student_id == student.id)
        .order_by(
            (ReviewCard.state == REVIEW_STATE_NEW).desc(),
            ReviewCard.due_at.asc().nulls_first(),
        )
        .all()
    )

    # Erişilebilir subject'ler (seed için) — öğrencinin sınıf seviyesi +
    # müfredat modeline göre filtrele. Aksi halde LGS öğrencisinde TYT/AYT
    # dersleri, YKS öğrencisinde 8. sınıf LGS dersleri karışıyor.
    from sqlalchemy import or_ as sa_or
    all_subjects = (
        db.query(Subject)
        .filter(
            sa_or(
                Subject.is_builtin.is_(True),
                Subject.teacher_id == user.id,
            )
        )
        .order_by(Subject.order, Subject.name)
        .all()
    )
    student_cmodel = student.effective_curriculum_model
    subjects = []
    seen_names: set[str] = set()
    for s in all_subjects:
        # Sınıf seviyesi uyumu
        if not s.covers_grade(student.grade_level, is_graduate=student.is_graduate):
            continue
        # Müfredat modeli uyumu (NULL = her modele uygun)
        if student_cmodel and s.curriculum_model and s.curriculum_model != student_cmodel:
            continue
        # Aynı ad farklı modellerde yaşayabilir — duplicate'i önle (örn.
        # "Matematik" hem LGS hem Maarif lise modelinde varsa, öğrencinin
        # modeline en uygun olan kalsın)
        if s.name in seen_names:
            continue
        seen_names.add(s.name)
        subjects.append(s)

    # A+C entegrasyonu — Zorlanılan konuları öğretmen önerisi olarak hazırla
    struggling = struggling_topics_for_student(
        db, student_id=student.id, limit=8, min_score=10.0
    )
    # Her zorlanılan konu için: bu öğrenciye atanmış BookSection'lar var mı?
    # Varsa "hızlı görev oluştur" linki hazır olsun.
    from app.models import BookSection, StudentBook
    struggle_cards: list[dict] = []
    if struggling:
        topic_ids = [s.topic_id for s in struggling]
        # Bu öğrencinin envanterindeki, ilgili topic'e ait section'lar
        sections_by_topic: dict[int, list[BookSection]] = {}
        rows = (
            db.query(BookSection)
            .options(joinedload(BookSection.book))
            .join(StudentBook, StudentBook.book_id == BookSection.book_id)
            .filter(
                StudentBook.student_id == student.id,
                BookSection.topic_id.in_(topic_ids),
            )
            .all()
        )
        for sec in rows:
            sections_by_topic.setdefault(sec.topic_id, []).append(sec)

        for st in struggling:
            secs = sections_by_topic.get(st.topic_id, [])
            struggle_cards.append({
                "topic_id": st.topic_id,
                "topic_name": st.topic_name,
                "subject_name": st.subject_name,
                "card_id": st.card_id,
                "state": st.state,
                "state_label": REVIEW_STATE_LABELS_TR.get(st.state, st.state),
                "difficulty": st.difficulty,
                "stability": st.stability,
                "lapse_count": st.lapse_count,
                "review_count": st.review_count,
                "score": st.score,
                "reasons": st.reasons,
                "sections": [
                    {
                        "id": s.id,
                        "book_id": s.book_id,
                        "book_name": s.book.name,
                        "label": s.label,
                        "test_count": s.test_count,
                    }
                    for s in secs
                ],
            })

    flash_ok = request.query_params.get("ok")
    flash_err = request.query_params.get("err")
    return templates.TemplateResponse(
        "teacher/student_review.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "cards": cards,
            "breakdown": breakdown,
            "subjects": subjects,
            "struggle_cards": struggle_cards,
            "state_labels": REVIEW_STATE_LABELS_TR,
            "rating_labels": RATING_LABELS_TR,
            "flash_ok": flash_ok,
            "flash_err": flash_err,
        },
    )


@router.post("/teacher/students/{student_id}/review/seed")
def teacher_seed_subject(
    student_id: int,
    subject_id: int = Form(...),
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
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı.")

    from sqlalchemy import or_ as sa_or
    subject = (
        db.query(Subject)
        .filter(
            Subject.id == subject_id,
            sa_or(Subject.is_builtin.is_(True), Subject.teacher_id == user.id),
        )
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Ders bulunamadı.")

    res = seed_subject_for_student(
        db, student=student, subject=subject, teacher=user
    )
    db.commit()
    parts = [f"{res.added} yeni kart eklendi"]
    if res.skipped_existing:
        parts.append(f"{res.skipped_existing} kart zaten vardı")
    msg = " · ".join(parts)
    return RedirectResponse(
        url=f"/teacher/students/{student_id}/review?ok={quote(msg)}",
        status_code=303,
    )


@router.get("/teacher/review")
def teacher_review_dashboard(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmenin tüm öğrencilerinin review yükü."""
    now = datetime.now(timezone.utc)
    rows = teacher_review_load(db, teacher_id=user.id, now=now)
    return templates.TemplateResponse(
        "teacher/review_dashboard.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
        },
    )
