"""Yanlış Soru Arşivi — API v2 router (öğrenci + koç yüzleri tek dosyada;
surveys.py deseni).

Öğrenci: kendi arşivi (ekle/foto/etiketle/yeniden çöz/sil).
Koç: kendi öğrencisinin arşivi (görüntüle + özet analitik + koç açıklaması +
öğrenci adına ekleme — seans senaryosu).
Veli: BİLİNÇLİ olarak erişemez (özel çalışma alanı).

Fotoğraflar DB'de saklanır; görüntüleme uçları sahiplik dışında 404 döner
(varlık sızıntısı yok).
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import (
    User,
    UserRole,
    WQ_ERROR_LABELS_TR,
    WQ_IMAGE_QUESTION,
    WQ_IMAGE_SOLUTION,
    WrongQuestion,
    WrongQuestionImage,
)
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.wrong_question import (
    AiTagResult,
    CoachNoteBody,
    TopicAccumulationOut,
    WrongQuestionAttemptBody,
    WrongQuestionCountsOut,
    WrongQuestionCreateBody,
    WrongQuestionImageRef,
    WrongQuestionItem,
    WrongQuestionListResponse,
    WrongQuestionSummaryResponse,
    WrongQuestionUpdateBody,
)
from app.services import wrong_question_service as svc

router = APIRouter(tags=["v2-wrong-questions"])


# ============================================================================
# Yardımcılar
# ============================================================================


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error": "not_found", "code": "wrong_question_not_found",
        "message": "Kayıt bulunamadı.",
    })


def _svc_error(e: svc.WrongQuestionError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "error": "validation" if e.status == 422 else "not_found",
        "code": e.code, "message": e.message,
    })


def _require_student(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız öğrenci hesabıyla kullanılabilir.",
        })
    return user


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız koç hesabıyla kullanılabilir.",
        })
    return user


def _get_owned_student(db: Session, coach: User, student_id: int) -> User:
    student = db.get(User, student_id)
    if (
        student is None
        or student.role != UserRole.STUDENT
        or student.teacher_id != coach.id
    ):
        raise _not_found()
    return student


def _to_item(wq: WrongQuestion, *, now=None) -> WrongQuestionItem:
    from datetime import datetime, timezone
    if now is None:
        now = datetime.now(timezone.utc)
    due_aware = svc.as_aware(wq.due_at)
    due_iso = due_aware.isoformat() if due_aware else None
    is_due = bool(
        wq.status == "acik" and due_aware is not None and due_aware <= now
    )
    return WrongQuestionItem(
        id=wq.id,
        status=wq.status,
        source_kind=wq.source_kind,
        error_type=wq.error_type,
        error_type_label=WQ_ERROR_LABELS_TR.get(wq.error_type) if wq.error_type else None,
        subject_id=wq.subject_id,
        subject_name=wq.subject.name if wq.subject else None,
        topic_id=wq.topic_id,
        topic_name=wq.topic.name if wq.topic else None,
        book_name=wq.book.name if wq.book else None,
        section_label=wq.section.label if wq.section else None,
        note=wq.note,
        coach_note=wq.coach_note,
        ai_question_text=wq.ai_question_text,
        ai_hint=wq.ai_hint,
        ai_tagged_at=(
            svc.as_aware(wq.ai_tagged_at).isoformat() if wq.ai_tagged_at else None
        ),
        difficulty_guess=wq.difficulty_guess,
        correct_streak=wq.correct_streak,
        attempts_count=wq.attempts_count,
        due_at=due_iso,
        is_due=is_due,
        closed_at=wq.closed_at.isoformat() if wq.closed_at else None,
        created_at=wq.created_at.isoformat() if wq.created_at else "",
        images=[
            WrongQuestionImageRef(
                id=im.id, kind=im.kind,
                content_type=im.content_type, size_bytes=im.size_bytes,
            )
            for im in wq.images
        ],
    )


def _list_response(db: Session, student_id: int, **filters) -> WrongQuestionListResponse:
    rows, counts = svc.list_for_student(db, student_id, **filters)
    return WrongQuestionListResponse(
        items=[_to_item(w) for w in rows],
        counts=WrongQuestionCountsOut(
            total=counts.total, open=counts.open,
            closed=counts.closed, due=counts.due,
        ),
        error_type_labels=WQ_ERROR_LABELS_TR,
    )


def _image_response(img: WrongQuestionImage) -> Response:
    return Response(
        content=img.data,
        media_type=img.content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(f'soru-{img.wrong_question_id}-{img.id}')}",
            "Content-Length": str(img.size_bytes),
            "Cache-Control": "private, no-store",
        },
    )


_STUDENT_INVALIDATE = ["student:wrong-questions"]


def _coach_invalidate(coach_id: int, student_id: int) -> list[str]:
    return [
        f"teacher:{coach_id}:students:{student_id}:wrong-questions",
        "student:wrong-questions",
    ]


# ============================================================================
# AI etiketleme (Faz 3) — ortak akış: öğrenci veya koç tetikler, KOÇ öder
# ============================================================================


def _run_ai_tag(
    db: Session,
    wq: WrongQuestion,
    *,
    student: User,
    actor: User,
    invalidate: list[str],
) -> MutationResponse[AiTagResult]:
    """Foto → Gemini vision → konu/zorluk/Sokratik ipucu; kayda uygular.

    Kapılar (veli içgörüsü deseni — üretim ÖĞRENCİNİN KOÇUNUN kaynağıyla yapılır):
      koç yok → 403 · koç ücretli değil → 403 · koç rıza vermemiş → 403 ·
      fotoğraf yok → 422 · kredi bitti → 402 · okunamadı → 422 · servis → 502
    """
    import base64

    from app.models import UsageKind
    from app.services import wrong_question_service as _svc
    from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
    from app.services.ai_wrong_question import tag_wrong_question_photo
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits
    from app.services.plans import ai_premium_allowed

    coach = db.get(User, student.teacher_id) if student.teacher_id else None
    if coach is None:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "no_coach",
            "message": "Yapay zekâ etiketleme için bağlı bir koç gerekir."})
    if not ai_premium_allowed(db, coach):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "plan_upgrade_required",
            "message": "Yapay zekâ etiketleme koçun paketinde aktif değil."})
    if coach.ai_capture_consent_at is None:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "consent_required",
            "message": "Koç henüz yapay zekâ onayını vermemiş."})

    img = _svc.primary_question_image(db, wq)
    if img is None:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "no_photo",
            "message": "Etiketleme için sorunun fotoğrafı gerekir."})

    candidates = _svc.candidate_topics(db, student, coach.id)
    b64 = base64.b64encode(img.data).decode("ascii")

    try:
        with consume_credits(
            db, owner=CreditOwner.for_user(coach), kind=UsageKind.AI_WRONG_TAG,
            actor_user_id=actor.id, autocommit=False,
        ) as ctx:
            result = tag_wrong_question_photo(
                b64, img.content_type, candidates=candidates,
            )
            ctx.set_metadata({
                "student_id": student.id, "wrong_question_id": wq.id,
                "candidates": len(candidates),
            })
    except CreditBlocked:
        db.rollback()
        raise HTTPException(status_code=402, detail={
            "error": "payment_required", "code": "ai_credit_exhausted",
            "message": "Koçun yapay zekâ kredisi bu ay için doldu."})
    except AIInvalidResponse as e:
        db.rollback()
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "photo_unreadable",
            "message": str(e) or "Fotoğraf okunamadı — daha net bir kare deneyin."})
    except AIServiceUnavailable as e:
        db.rollback()
        raise HTTPException(status_code=502, detail={
            "error": "upstream_unavailable", "code": "ai_unavailable",
            "message": f"Yapay zekâ servisi şu an kullanılamıyor: {e}"})

    had_topic = wq.topic_id is not None
    _svc.apply_ai_tags(db, wq, result)
    db.commit()
    db.refresh(wq)

    from app.services.credits import KIND_CREDITS
    return MutationResponse[AiTagResult](
        data=AiTagResult(
            item=_to_item(wq),
            # AI'ın İDDİASI değil, kayda GERÇEKTEN uygulanan sonuç raporlanır
            # (uydurma/geçersiz konu düşürülmüşse "eşleşti" denmez).
            matched_topic=(not had_topic) and wq.topic_id is not None,
            hint_created=bool(wq.ai_hint),
            credits_charged=KIND_CREDITS.get(UsageKind.AI_WRONG_TAG, 2),
        ),
        invalidate=invalidate,
    )


# ============================================================================
# ÖĞRENCİ uçları
# ============================================================================


@router.get("/student/wrong-questions", response_model=WrongQuestionListResponse)
def student_list_wrong_questions(
    status: str | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    error_type: str | None = Query(default=None),
    source_kind: str | None = Query(default=None),
    due: bool = Query(default=False, description="yalnız vadesi gelmiş (yeniden çözülecek)"),
    q: str | None = Query(default=None, max_length=120),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrencinin yanlış soru arşivi (filtreli) + sayaçlar."""
    return _list_response(
        db, user.id, status=status, subject_id=subject_id, topic_id=topic_id,
        error_type=error_type, source_kind=source_kind, due_only=due, q=q,
    )


@router.post(
    "/student/wrong-questions",
    response_model=MutationResponse[WrongQuestionItem],
)
async def student_create_wrong_question(
    photos: list[UploadFile] = File(default=[]),
    source_kind: str | None = Form(default=None),
    book_section_id: int | None = Form(default=None),
    task_id: int | None = Form(default=None),
    exam_result_id: int | None = Form(default=None),
    subject_id: int | None = Form(default=None),
    topic_id: int | None = Form(default=None),
    error_type: str | None = Form(default=None),
    note: str | None = Form(default=None),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Yanlış soru ekle (multipart: 0..N soru fotoğrafı + bağlam alanları).

    Sıfır sürtünme: yalnız fotoğrafla da (etiketsiz) kaydedilebilir; görev/bölüm
    bağlamı verildiyse ders+konu kendiliğinden dolar.
    """
    try:
        wq = svc.create_wrong_question(
            db, user, created_by=user,
            source_kind=source_kind or "diger",
            book_section_id=book_section_id, task_id=task_id,
            exam_result_id=exam_result_id, subject_id=subject_id,
            topic_id=topic_id, error_type=error_type, note=note,
        )
        for up in (photos or []):
            data = await up.read()
            svc.add_image(
                db, wq, kind=WQ_IMAGE_QUESTION,
                content_type=up.content_type or "", data=data,
            )
    except svc.WrongQuestionError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(wq)
    return MutationResponse[WrongQuestionItem](
        data=_to_item(wq), invalidate=_STUDENT_INVALIDATE,
    )


@router.get("/student/wrong-questions/{wq_id}", response_model=WrongQuestionItem)
def student_get_wrong_question(
    wq_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    wq = svc.get_for_student(db, user, wq_id)
    if wq is None:
        raise _not_found()
    return _to_item(wq)


@router.post(
    "/student/wrong-questions/{wq_id}",
    response_model=MutationResponse[WrongQuestionItem],
)
def student_update_wrong_question(
    wq_id: int,
    body: WrongQuestionUpdateBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Etiket/not düzeltme (AI önerisini onaylama dahil)."""
    wq = svc.get_for_student(db, user, wq_id)
    if wq is None:
        raise _not_found()
    try:
        svc.update_tags(
            db, wq, subject_id=body.subject_id, topic_id=body.topic_id,
            error_type=body.error_type, note=body.note, clear_note=body.clear_note,
        )
    except svc.WrongQuestionError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(wq)
    return MutationResponse[WrongQuestionItem](
        data=_to_item(wq), invalidate=_STUDENT_INVALIDATE,
    )


@router.post(
    "/student/wrong-questions/{wq_id}/images",
    response_model=MutationResponse[WrongQuestionItem],
)
async def student_add_image(
    wq_id: int,
    file: UploadFile = File(...),
    kind: str = Form(default=WQ_IMAGE_QUESTION),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Soruya fotoğraf ekle (kind=question|solution — çözüm fotoğrafı dahil)."""
    wq = svc.get_for_student(db, user, wq_id)
    if wq is None:
        raise _not_found()
    data = await file.read()
    try:
        svc.add_image(db, wq, kind=kind, content_type=file.content_type or "", data=data)
    except svc.WrongQuestionError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(wq)
    return MutationResponse[WrongQuestionItem](
        data=_to_item(wq), invalidate=_STUDENT_INVALIDATE,
    )


@router.get("/student/wrong-questions/{wq_id}/images/{image_id}")
def student_get_image(
    wq_id: int,
    image_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    wq = svc.get_for_student(db, user, wq_id)
    if wq is None:
        raise _not_found()
    img = db.get(WrongQuestionImage, image_id)
    if img is None or img.wrong_question_id != wq.id:
        raise _not_found()
    return _image_response(img)


@router.post(
    "/student/wrong-questions/{wq_id}/attempt",
    response_model=MutationResponse[WrongQuestionItem],
)
def student_attempt(
    wq_id: int,
    body: WrongQuestionAttemptBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Yeniden çözme sonucu: 1=yine yanlış · 2=zor · 3=çözdüm · 4=kolay.

    FSRS bir sonraki vadeyi kurar; aralıklı 2 başarılı çözüm soruyu KAPATIR,
    'yine yanlış' kapalı soruyu YENİDEN AÇAR.
    """
    wq = svc.get_for_student(db, user, wq_id)
    if wq is None:
        raise _not_found()
    try:
        svc.record_attempt(db, wq, body.rating)
    except svc.WrongQuestionError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(wq)
    return MutationResponse[WrongQuestionItem](
        data=_to_item(wq), invalidate=_STUDENT_INVALIDATE,
    )


@router.post(
    "/student/wrong-questions/{wq_id}/ai-tag",
    response_model=MutationResponse[AiTagResult],
)
def student_ai_tag(
    wq_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Fotoğraftan AI etiketleme: konu eşleme + zorluk + Sokratik ipucu.

    Kredi/paket/rıza öğrencinin KOÇUNA aittir (öğrencinin kredi havuzu yok) —
    veli içgörüsüyle aynı model. AI tam çözüm VERMEZ (yalnız yaklaşım ipucu).
    """
    wq = svc.get_for_student(db, user, wq_id)
    if wq is None:
        raise _not_found()
    return _run_ai_tag(db, wq, student=user, actor=user,
                       invalidate=_STUDENT_INVALIDATE)


@router.delete(
    "/student/wrong-questions/{wq_id}",
    response_model=MutationResponse[dict],
)
def student_delete_wrong_question(
    wq_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    wq = svc.get_for_student(db, user, wq_id)
    if wq is None:
        raise _not_found()
    db.delete(wq)   # images cascade (delete-orphan)
    db.commit()
    return MutationResponse[dict](
        data={"deleted": True}, invalidate=_STUDENT_INVALIDATE,
    )


# ============================================================================
# KOÇ uçları
# ============================================================================


@router.get(
    "/teacher/students/{student_id}/wrong-questions",
    response_model=WrongQuestionListResponse,
)
def teacher_list_wrong_questions(
    student_id: int,
    status: str | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    error_type: str | None = Query(default=None),
    source_kind: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(db, user, student_id)
    return _list_response(
        db, student.id, status=status, subject_id=subject_id, topic_id=topic_id,
        error_type=error_type, source_kind=source_kind, q=q,
    )


@router.get(
    "/teacher/students/{student_id}/wrong-questions/summary",
    response_model=WrongQuestionSummaryResponse,
)
def teacher_wrong_questions_summary(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Koç tanı özeti: en çok biriken konular + hata türü dağılımı + kapanış hızı."""
    student = _get_owned_student(db, user, student_id)
    s = svc.coach_summary(db, student.id)
    return WrongQuestionSummaryResponse(
        counts=WrongQuestionCountsOut(
            total=s.counts.total, open=s.counts.open,
            closed=s.counts.closed, due=s.counts.due,
        ),
        by_topic=[
            TopicAccumulationOut(
                topic_id=t.topic_id, topic_name=t.topic_name,
                subject_name=t.subject_name,
                open_count=t.open_count, closed_count=t.closed_count,
            )
            for t in s.by_topic
        ],
        by_error_type=s.by_error_type,
        error_type_labels=WQ_ERROR_LABELS_TR,
        closed_last_30d=s.closed_last_30d,
        added_last_30d=s.added_last_30d,
    )


@router.post(
    "/teacher/students/{student_id}/wrong-questions",
    response_model=MutationResponse[WrongQuestionItem],
)
def teacher_create_wrong_question(
    student_id: int,
    body: WrongQuestionCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Koç, seansta öğrenci adına yanlış kaydı açar (fotoğrafı öğrenci ekler
    veya koç images ucundan yükler)."""
    student = _get_owned_student(db, user, student_id)
    try:
        wq = svc.create_wrong_question(
            db, student, created_by=user,
            source_kind=body.source_kind or "diger",
            book_section_id=body.book_section_id, task_id=body.task_id,
            exam_result_id=body.exam_result_id, subject_id=body.subject_id,
            topic_id=body.topic_id, error_type=body.error_type, note=body.note,
        )
    except svc.WrongQuestionError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(wq)
    return MutationResponse[WrongQuestionItem](
        data=_to_item(wq), invalidate=_coach_invalidate(user.id, student.id),
    )


@router.post(
    "/teacher/wrong-questions/{wq_id}/coach-note",
    response_model=MutationResponse[WrongQuestionItem],
)
def teacher_set_coach_note(
    wq_id: int,
    body: CoachNoteBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Koç açıklaması (çözüm yaklaşımı) — öğrenci kartta görür."""
    wq = svc.get_for_coach(db, user, wq_id)
    if wq is None:
        raise _not_found()
    wq.coach_note = (body.coach_note or "").strip() or None
    db.commit()
    db.refresh(wq)
    return MutationResponse[WrongQuestionItem](
        data=_to_item(wq), invalidate=_coach_invalidate(user.id, wq.student_id),
    )


@router.post(
    "/teacher/wrong-questions/{wq_id}/ai-tag",
    response_model=MutationResponse[AiTagResult],
)
def teacher_ai_tag(
    wq_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Koç, öğrencinin arşivlediği soruyu AI ile etiketler (kendi kredisinden)."""
    wq = svc.get_for_coach(db, user, wq_id)
    if wq is None:
        raise _not_found()
    student = db.get(User, wq.student_id)
    if student is None:
        raise _not_found()
    return _run_ai_tag(db, wq, student=student, actor=user,
                       invalidate=_coach_invalidate(user.id, student.id))


@router.get("/teacher/wrong-questions/{wq_id}/images/{image_id}")
def teacher_get_image(
    wq_id: int,
    image_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    wq = svc.get_for_coach(db, user, wq_id)
    if wq is None:
        raise _not_found()
    img = db.get(WrongQuestionImage, image_id)
    if img is None or img.wrong_question_id != wq.id:
        raise _not_found()
    return _image_response(img)
