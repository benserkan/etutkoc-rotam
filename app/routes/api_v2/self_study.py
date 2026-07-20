"""Bağımsız çalışma kayıtları — API v2 router (öğrenci + koç tek dosyada;
wrong_questions.py deseni).

Tatil/koçsuz dönemde öğrencinin program DIŞINDA çözdüğü testler:
- Öğrenci BEYAN eder (pending; ilerlemeye dokunmaz) → koç onaylar/reddeder.
- Koç doğrudan toplu girer (anında onaylı + uygulanır) — izli (kim/ne zaman/
  kaç test/hangi dönem). Kurum şeffaflığı Faz 2'de bu kayıtlardan okunur.

İlerleme yazımının tamamı self_study_service üzerinden (TEK MERKEZ).
Sahiplik dışı her şey 404 (varlık sızıntısı yok). Veli erişemez.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.deps import get_db
from app.models import (
    AuditAction,
    SS_SOURCE_COACH,
    SS_SOURCE_LABELS_TR,
    SS_SOURCE_STUDENT,
    SS_STATUS_APPROVED,
    SS_STATUS_LABELS_TR,
    SS_STATUS_PENDING,
    Book,
    BookSection,
    SelfStudyEntry,
    StudentBook,
    User,
    UserRole,
)
from app.models.book import BOOK_TYPE_LABELS
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.self_study import (
    SelfStudyCreateBody,
    SelfStudyCreateResult,
    SelfStudyDeleteResult,
    SelfStudyEntryItem,
    SelfStudyListResponse,
    SelfStudyOptionBook,
    SelfStudyOptionSection,
    SelfStudyOptionsResponse,
    SelfStudyReviewBody,
    SelfStudySkippedItem,
)
from app.services import self_study_service as svc
from app.services.audit import log_action

router = APIRouter(tags=["v2-self-study"])


# ============================================================================
# Yardımcılar
# ============================================================================


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error": "not_found", "code": "self_study_not_found",
        "message": "Kayıt bulunamadı.",
    })


def _svc_error(e: svc.SelfStudyError) -> HTTPException:
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


def _to_item(e: SelfStudyEntry) -> SelfStudyEntryItem:
    book = e.student_book.book if e.student_book else None
    return SelfStudyEntryItem(
        id=e.id,
        student_book_id=e.student_book_id,
        book_id=(book.id if book else 0),
        book_name=(book.name if book else "—"),
        subject_name=(book.subject.name if book and book.subject else "—"),
        section_id=e.book_section_id,
        section_label=(e.section.label if e.section else "—"),
        test_count=e.test_count,
        applied_count=e.applied_count,
        source=e.source,
        source_label=SS_SOURCE_LABELS_TR.get(e.source, e.source),
        status=e.status,
        status_label=SS_STATUS_LABELS_TR.get(e.status, e.status),
        note=e.note,
        period_start=e.period_start.isoformat() if e.period_start else None,
        period_end=e.period_end.isoformat() if e.period_end else None,
        created_by_name=(e.created_by.full_name if e.created_by else None),
        created_at=e.created_at.isoformat() if e.created_at else "",
        reviewed_at=e.reviewed_at.isoformat() if e.reviewed_at else None,
        review_note=e.review_note,
    )


def _list_response(db: Session, student_id: int) -> SelfStudyListResponse:
    items, pending = svc.list_for_student(db, student_id)
    return SelfStudyListResponse(
        items=[_to_item(e) for e in items], pending_count=pending,
    )


def _resolve_items(
    db: Session, student: User, body: SelfStudyCreateBody
) -> list[tuple[StudentBook, BookSection, int]]:
    """Body kalemlerini sahiplik doğrulamasıyla (öğrencinin kitabı + kitabın
    bölümü) ORM nesnelerine çözer. Uyuşmayan kalem → 404 (sızıntı yok)."""
    resolved: list[tuple[StudentBook, BookSection, int]] = []
    for it in body.items:
        sb = (
            db.query(StudentBook)
            .options(joinedload(StudentBook.book))
            .filter(
                StudentBook.id == it.student_book_id,
                StudentBook.student_id == student.id,
            )
            .first()
        )
        if not sb:
            raise _not_found()
        section = (
            db.query(BookSection)
            .filter(
                BookSection.id == it.section_id,
                BookSection.book_id == sb.book_id,
            )
            .first()
        )
        if not section:
            raise _not_found()
        resolved.append((sb, section, it.test_count))
    return resolved


def _get_entry_for_coach(db: Session, coach: User, entry_id: int) -> SelfStudyEntry:
    e = (
        db.query(SelfStudyEntry)
        .options(
            joinedload(SelfStudyEntry.section),
            joinedload(SelfStudyEntry.student_book).joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(SelfStudyEntry.student),
        )
        .filter(SelfStudyEntry.id == entry_id)
        .first()
    )
    if not e or not e.student or e.student.teacher_id != coach.id:
        raise _not_found()
    return e


def _push_bg(user_id: int | None, title: str, body: str, data: dict) -> None:
    """BackgroundTasks hedefi — taze session ile best-effort push."""
    if not user_id:
        return
    from app.services.push_notifications import safe_push

    db = SessionLocal()
    try:
        safe_push(db, user_id=user_id, title=title, body=body, data=data)
    finally:
        db.close()


def _teacher_invalidate(coach_id: int, student_id: int) -> list[str]:
    return [
        f"teacher:{coach_id}:students:{student_id}:books",
        f"teacher:{coach_id}:students:{student_id}:self-study",
        f"teacher:{coach_id}:students:{student_id}:summary",
        f"teacher:{coach_id}:students:{student_id}",
        "student:books",
        "student:self-study",
    ]


def _create_result(
    created: list[SelfStudyEntry], skipped: list[dict]
) -> SelfStudyCreateResult:
    return SelfStudyCreateResult(
        created=[_to_item(e) for e in created],
        skipped=[SelfStudySkippedItem(**s) for s in skipped],
        applied_total=sum(e.applied_count for e in created),
        pending_total=sum(
            e.test_count for e in created if e.status == SS_STATUS_PENDING
        ),
    )


# ============================================================================
# Koç uçları
# ============================================================================


@router.get(
    "/teacher/students/{student_id}/self-study",
    response_model=SelfStudyListResponse,
)
def teacher_self_study_list_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(db, user, student_id)
    return _list_response(db, student.id)


@router.post(
    "/teacher/students/{student_id}/self-study",
    response_model=MutationResponse[SelfStudyCreateResult],
)
def teacher_self_study_create_v2(
    student_id: int,
    body: SelfStudyCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Koç toplu girişi — anında onaylı + ilerlemeye uygulanır (izli + audit)."""
    student = _get_owned_student(db, user, student_id)
    items = _resolve_items(db, student, body)
    try:
        created, skipped = svc.create_entries(
            db,
            student=student,
            actor=user,
            source=SS_SOURCE_COACH,
            items=items,
            note=body.note,
            period_start=body.period_start,
            period_end=body.period_end,
        )
    except svc.SelfStudyError as e:
        raise _svc_error(e)
    log_action(
        db,
        action=AuditAction.SELF_STUDY_UPDATE,
        actor_id=user.id,
        target_type="user",
        target_id=student.id,
        request=request,
        details={
            "op": "coach_create",
            "entries": len(created),
            "applied_total": sum(e.applied_count for e in created),
            "skipped": len(skipped),
            "sections": [
                {"section_id": e.book_section_id, "applied": e.applied_count}
                for e in created
            ][:30],
            "note": body.note,
            "period_start": str(body.period_start) if body.period_start else None,
            "period_end": str(body.period_end) if body.period_end else None,
        },
        autocommit=False,
    )
    db.commit()
    for e in created:
        db.refresh(e)
    return MutationResponse[SelfStudyCreateResult](
        data=_create_result(created, skipped),
        invalidate=_teacher_invalidate(user.id, student.id),
    )


@router.post(
    "/teacher/self-study/{entry_id}/review",
    response_model=MutationResponse[SelfStudyEntryItem],
)
def teacher_self_study_review_v2(
    entry_id: int,
    body: SelfStudyReviewBody,
    background: BackgroundTasks,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Bekleyen öğrenci beyanını onayla (ilerlemeye uygula) / reddet."""
    entry = _get_entry_for_coach(db, user, entry_id)
    try:
        svc.review_entry(
            db, entry,
            approve=body.approve,
            reviewer=user,
            review_note=body.review_note,
        )
    except svc.SelfStudyError as e:
        raise _svc_error(e)
    student = entry.student
    log_action(
        db,
        action=AuditAction.SELF_STUDY_UPDATE,
        actor_id=user.id,
        target_type="user",
        target_id=student.id,
        request=request,
        details={
            "op": "approve" if body.approve else "reject",
            "entry_id": entry.id,
            "section_id": entry.book_section_id,
            "test_count": entry.test_count,
            "applied": entry.applied_count,
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(entry)
    verdict = "onayladı" if entry.status == SS_STATUS_APPROVED else "reddetti"
    background.add_task(
        _push_bg,
        student.id,
        "Bağımsız çalışma",
        f"Koçun bağımsız çalışma bildirimini {verdict}"
        + (f" ({entry.applied_count} test işlendi)." if entry.status == SS_STATUS_APPROVED else "."),
        {"type": "student", "screen": "books"},
    )
    return MutationResponse[SelfStudyEntryItem](
        data=_to_item(entry),
        invalidate=_teacher_invalidate(user.id, student.id),
    )


@router.delete(
    "/teacher/self-study/{entry_id}",
    response_model=MutationResponse[SelfStudyDeleteResult],
)
def teacher_self_study_delete_v2(
    entry_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Kaydı sil — uygulanmışsa ilerlemeden birebir geri alınır (audit izli)."""
    entry = _get_entry_for_coach(db, user, entry_id)
    student_id = entry.student_id
    details = {
        "op": "delete",
        "entry_id": entry.id,
        "section_id": entry.book_section_id,
        "source": entry.source,
        "status": entry.status,
        "test_count": entry.test_count,
    }
    reverted = svc.delete_entry(db, entry)
    details["reverted"] = reverted
    log_action(
        db,
        action=AuditAction.SELF_STUDY_UPDATE,
        actor_id=user.id,
        target_type="user",
        target_id=student_id,
        request=request,
        details=details,
        autocommit=False,
    )
    db.commit()
    return MutationResponse[SelfStudyDeleteResult](
        data=SelfStudyDeleteResult(deleted_id=entry_id, reverted_count=reverted),
        invalidate=_teacher_invalidate(user.id, student_id),
    )


# ============================================================================
# Öğrenci uçları
# ============================================================================


@router.get("/student/self-study", response_model=SelfStudyListResponse)
def student_self_study_list_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    return _list_response(db, user.id)


@router.get("/student/self-study/options", response_model=SelfStudyOptionsResponse)
def student_self_study_options_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Beyan dialogu için kitap → bölüm + kalan kapasite listesi."""
    sbs = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == user.id)
        .all()
    )
    books: list[SelfStudyOptionBook] = []
    for sb in sbs:
        book = sb.book
        if not book:
            continue
        pmap = {p.book_section_id: p for p in sb.section_progress}
        sections = []
        for s in sorted(book.sections, key=lambda x: (x.order, x.id)):
            sp = pmap.get(s.id)
            completed = sp.completed_count if sp else 0
            reserved = sp.reserved_count if sp else 0
            sections.append(SelfStudyOptionSection(
                section_id=s.id,
                label=s.label,
                test_count=s.test_count,
                completed_count=completed,
                reserved_count=reserved,
                remaining=max(0, s.test_count - completed - reserved),
            ))
        if not sections:
            continue
        books.append(SelfStudyOptionBook(
            student_book_id=sb.id,
            book_id=book.id,
            book_name=book.name,
            subject_name=(book.subject.name if book.subject else "—"),
            book_type_label=BOOK_TYPE_LABELS.get(book.type, "—") if book.type else "—",
            sections=sections,
        ))
    books.sort(key=lambda b: (b.subject_name.lower(), b.book_name.lower()))
    return SelfStudyOptionsResponse(books=books)


@router.post("/student/self-study", response_model=MutationResponse[SelfStudyCreateResult])
def student_self_study_declare_v2(
    body: SelfStudyCreateBody,
    background: BackgroundTasks,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrenci beyanı — pending; koç onaylayınca ilerlemeye işlenir."""
    items = _resolve_items(db, user, body)
    try:
        created, skipped = svc.create_entries(
            db,
            student=user,
            actor=user,
            source=SS_SOURCE_STUDENT,
            items=items,
            note=body.note,
            period_start=body.period_start,
            period_end=body.period_end,
        )
    except svc.SelfStudyError as e:
        raise _svc_error(e)
    db.commit()
    for e in created:
        db.refresh(e)
    total = sum(e.test_count for e in created)
    if created and user.teacher_id:
        background.add_task(
            _push_bg,
            user.teacher_id,
            "Bağımsız çalışma bildirimi",
            f"{user.full_name} program dışı çalışma bildirdi ({total} test) — onayını bekliyor.",
            {"type": "coach_student", "student_id": user.id},
        )
    coach_keys = (
        [
            f"teacher:{user.teacher_id}:students:{user.id}:self-study",
            f"teacher:{user.teacher_id}:students:{user.id}:books",
        ]
        if user.teacher_id
        else []
    )
    return MutationResponse[SelfStudyCreateResult](
        data=_create_result(created, skipped),
        invalidate=["student:self-study"] + coach_keys,
    )


@router.delete(
    "/student/self-study/{entry_id}",
    response_model=MutationResponse[SelfStudyDeleteResult],
)
def student_self_study_withdraw_v2(
    entry_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrenci yalnız BEKLEYEN kendi beyanını geri çekebilir."""
    entry = (
        db.query(SelfStudyEntry)
        .filter(SelfStudyEntry.id == entry_id, SelfStudyEntry.student_id == user.id)
        .first()
    )
    if not entry:
        raise _not_found()
    if entry.status != SS_STATUS_PENDING:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "not_pending",
            "message": "Sonuçlanmış kayıt geri çekilemez — koçunla konuş.",
        })
    svc.delete_entry(db, entry)
    db.commit()
    coach_keys = (
        [f"teacher:{user.teacher_id}:students:{user.id}:self-study"]
        if user.teacher_id
        else []
    )
    return MutationResponse[SelfStudyDeleteResult](
        data=SelfStudyDeleteResult(deleted_id=entry_id, reverted_count=0),
        invalidate=["student:self-study"] + coach_keys,
    )
