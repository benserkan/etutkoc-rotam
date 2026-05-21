"""API v2 — Öğretmen kitap kütüphanesi (Dalga 3 Paket 8).

Endpoint haritası (tümü prefix `/teacher/library`):
  Books:
    GET    /books                                  → BookListResponse
    POST   /books                                  → MutationResponse[BookDetailResponse]
    GET    /books/{id}                             → BookDetailResponse
    PATCH  /books/{id}                             → MutationResponse[BookDetailResponse]
    DELETE /books/{id}                             → MutationResponse[DeletedRef]
    POST   /books/{id}/clear-sections              → MutationResponse[DeletedRef]
    POST   /books/{id}/ai-suggest                  → MutationResponse[AiSuggestResult]
    POST   /books/{id}/save-as-template            → MutationResponse[BookTemplateListItem]
    POST   /books/{id}/apply-template              → MutationResponse[ApplyTemplateResult]
    PATCH  /books/{id}/assignments                 → MutationResponse[AssignmentsResult]

  Sections:
    POST   /books/{id}/sections                    → MutationResponse[BookSectionItem]
    POST   /books/{id}/sections/bulk-from-catalog  → MutationResponse[BulkCatalogResult]
    PATCH  /books/{id}/sections/{section_id}       → MutationResponse[BookSectionItem]
    DELETE /books/{id}/sections/{section_id}       → MutationResponse[DeletedRef]

  Templates:
    GET    /templates                              → BookTemplateListResponse
    DELETE /templates/{template_id}                → MutationResponse[DeletedRef]
    POST   /templates/{template_id}/verify         → MutationResponse[BookTemplateListItem]

  Book sets:
    GET    /book-sets                              → BookSetListResponse
    POST   /book-sets                              → MutationResponse[BookSetDetailResponse]
    GET    /book-sets/{set_id}                     → BookSetDetailResponse
    PATCH  /book-sets/{set_id}                     → MutationResponse[BookSetDetailResponse]
    DELETE /book-sets/{set_id}                     → MutationResponse[DeletedRef]
    POST   /book-sets/{set_id}/books               → MutationResponse[AddBooksToSetResult]
    DELETE /book-sets/{set_id}/books/{book_id}     → MutationResponse[DeletedRef]

  Yardımcı:
    GET    /subjects                               → SubjectListResponse
    GET    /subjects/{subject_id}/topics           → TopicListResponse

Cross-tenant 404 davranışı tüm uçlarda: `book_not_found`, `template_not_found`,
`book_set_not_found`, `section_not_found`, `subject_not_found`.

Rezerv invariant'ı (R-024): section/book silme veya overwrite işlemleri
SectionProgress.reserved_count > 0 veya completed_count > 0 olan satırlar
varsa 409 `has_reservations` / `has_progress` ile reddedilir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    Book,
    BookSection,
    BookSet,
    BookSetItem,
    BookTemplate,
    BookTemplateSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.library import (
    AddBooksToSetBody,
    AddBooksToSetResult,
    AiSuggestBody,
    AiSuggestResult,
    ApplyTemplateBody,
    ApplyTemplateResult,
    AssignedStudentRef,
    AssignmentsPatchBody,
    AssignmentsResult,
    BookCreateBody,
    BookDetailResponse,
    BookListItem,
    BookListResponse,
    BookPatchBody,
    BookSectionItem,
    BookSetAssignedStudent,
    BookSetCreateBody,
    BookSetDetailResponse,
    BookSetGradeBucket,
    BookSetListItem,
    BookSetListResponse,
    BookSetMemberRef,
    BookSetPatchBody,
    BookTemplateListItem,
    BookTemplateListResponse,
    BulkCatalogResult,
    DeletedRef,
    SaveAsTemplateBody,
    SectionCreateBody,
    SectionPatchBody,
    SectionsBulkFromCatalogBody,
    SubjectListResponse,
    SubjectRef,
    TopicListResponse,
    TopicRef,
)


router = APIRouter(prefix="/teacher/library", tags=["v2-teacher-library"])


# =============================================================================
# Auth kapısı (teacher.py ile aynı)
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


def _conflict(code: str, message: str, details: dict | None = None) -> HTTPException:
    detail = {"error": "conflict", "code": code, "message": message}
    if details:
        detail["details"] = details
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


# =============================================================================
# Ortak yardımcılar
# =============================================================================


def _get_owned_book(db: Session, book_id: int, teacher_id: int) -> Book:
    book = (
        db.query(Book)
        .options(
            joinedload(Book.subject),
            joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(Book.student_books).joinedload(StudentBook.student),
            joinedload(Book.student_books)
            .joinedload(StudentBook.section_progress),
        )
        .filter(Book.id == book_id, Book.teacher_id == teacher_id)
        .first()
    )
    if not book:
        raise _not_found("book_not_found", "Kitap bulunamadı.")
    return book


def _get_owned_template(db: Session, template_id: int, teacher_id: int) -> BookTemplate:
    tpl = (
        db.query(BookTemplate)
        .options(joinedload(BookTemplate.sections))
        .filter(BookTemplate.id == template_id, BookTemplate.teacher_id == teacher_id)
        .first()
    )
    if not tpl:
        raise _not_found("template_not_found", "Şablon bulunamadı.")
    return tpl


def _get_owned_book_set(db: Session, set_id: int, teacher_id: int) -> BookSet:
    bs = (
        db.query(BookSet)
        .options(
            joinedload(BookSet.items).joinedload(BookSetItem.book).joinedload(Book.subject),
        )
        .filter(BookSet.id == set_id, BookSet.teacher_id == teacher_id)
        .first()
    )
    if not bs:
        raise _not_found("book_set_not_found", "Kitap seti bulunamadı.")
    return bs


def _section_progress_totals(
    db: Session, section_id: int,
) -> tuple[int, int]:
    """Bir section için tüm öğrencilerin rezerv+tamam toplamı."""
    row = (
        db.query(
            func.coalesce(func.sum(SectionProgress.reserved_count), 0),
            func.coalesce(func.sum(SectionProgress.completed_count), 0),
        )
        .filter(SectionProgress.book_section_id == section_id)
        .first()
    )
    if row is None:
        return 0, 0
    return int(row[0] or 0), int(row[1] or 0)


def _build_section_item(db: Session, sec: BookSection) -> BookSectionItem:
    reserved, completed = _section_progress_totals(db, sec.id)
    return BookSectionItem(
        id=sec.id,
        label=sec.label,
        test_count=sec.test_count,
        order=sec.order,
        topic_id=sec.topic_id,
        topic_name=sec.topic.name if sec.topic else None,
        reserved_total=reserved,
        completed_total=completed,
        has_progress=(reserved > 0 or completed > 0),
    )


def _build_book_list_item(book: Book) -> BookListItem:
    sections = book.sections or []
    return BookListItem(
        id=book.id,
        name=book.name,
        publisher=book.publisher,
        type=book.type.value if book.type else "soru_bankasi",
        subject_id=book.subject_id,
        subject_name=book.subject.name if book.subject else None,
        avg_questions_per_test=book.avg_questions_per_test,
        target_grade_min=book.target_grade_min,
        target_grade_max=book.target_grade_max,
        target_graduate=bool(book.target_graduate),
        section_count=len(sections),
        total_tests=sum(s.test_count for s in sections),
        assigned_student_count=len(book.student_books or []),
        created_at=book.created_at,
    )


def _build_book_detail(db: Session, book: Book) -> BookDetailResponse:
    sections = sorted(book.sections or [], key=lambda s: (s.order, s.id))
    section_items = [_build_section_item(db, s) for s in sections]
    # Atanmış öğrencileri ilerleme bilgisiyle döndür
    assigned: list[AssignedStudentRef] = []
    for sb in book.student_books or []:
        has_p = any(
            (p.reserved_count > 0 or p.completed_count > 0)
            for p in (sb.section_progress or [])
        )
        assigned.append(AssignedStudentRef(
            student_id=sb.student_id,
            full_name=sb.student.full_name if sb.student else "—",
            has_progress=has_p,
        ))
    return BookDetailResponse(
        id=book.id,
        name=book.name,
        publisher=book.publisher,
        type=book.type.value if book.type else "soru_bankasi",
        subject_id=book.subject_id,
        subject_name=book.subject.name if book.subject else None,
        avg_questions_per_test=book.avg_questions_per_test,
        target_grade_min=book.target_grade_min,
        target_grade_max=book.target_grade_max,
        target_graduate=bool(book.target_graduate),
        created_at=book.created_at,
        sections=section_items,
        assigned_students=assigned,
        total_tests=sum(s.test_count for s in sections),
    )


def _build_template_item(db: Session, tpl: BookTemplate) -> BookTemplateListItem:
    subject_name: str | None = None
    if tpl.subject_id is not None:
        row = db.query(Subject.name).filter(Subject.id == tpl.subject_id).first()
        subject_name = row[0] if row else None
    return BookTemplateListItem(
        id=tpl.id,
        name=tpl.name,
        type=tpl.type.value if tpl.type else "soru_bankasi",
        publisher=tpl.publisher,
        subject_id=tpl.subject_id,
        subject_name=subject_name,
        target_grade_min=tpl.target_grade_min,
        target_grade_max=tpl.target_grade_max,
        target_graduate=bool(tpl.target_graduate),
        is_ai_generated=bool(tpl.is_ai_generated),
        is_verified=bool(tpl.is_verified),
        section_count=len(tpl.sections or []),
        created_at=tpl.created_at,
    )


def _invalidate_book(teacher_id: int, book_id: int | None = None) -> list[str]:
    keys = [
        f"teacher:{teacher_id}:library:books",
        f"teacher:{teacher_id}:library:templates",
    ]
    if book_id is not None:
        keys.append(f"teacher:{teacher_id}:library:books:{book_id}")
    return keys


def _invalidate_set(teacher_id: int, set_id: int | None = None) -> list[str]:
    keys = [f"teacher:{teacher_id}:library:book-sets"]
    if set_id is not None:
        keys.append(f"teacher:{teacher_id}:library:book-sets:{set_id}")
    return keys


def _invalidate_assignments(
    teacher_id: int, book_id: int, student_ids: list[int],
) -> list[str]:
    keys = _invalidate_book(teacher_id, book_id)
    for sid in student_ids:
        keys.append(f"teacher:{teacher_id}:students:{sid}:books")
    return keys


# =============================================================================
# Yardımcı listeler (subjects + topics)
# =============================================================================


def _accessible_subjects(db: Session, teacher_id: int) -> list[Subject]:
    return (
        db.query(Subject)
        .filter(or_(Subject.is_builtin.is_(True), Subject.teacher_id == teacher_id))
        .order_by(Subject.order, Subject.name)
        .all()
    )


def _accessible_topics(
    db: Session, subject_id: int, teacher_id: int,
) -> list[Topic]:
    return (
        db.query(Topic)
        .filter(
            Topic.subject_id == subject_id,
            or_(Topic.is_builtin.is_(True), Topic.teacher_id == teacher_id),
        )
        .order_by(Topic.order, Topic.name)
        .all()
    )


@router.get("/subjects", response_model=SubjectListResponse)
def library_subjects_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    subjects = _accessible_subjects(db, user.id)
    items = [
        SubjectRef(
            id=s.id,
            name=s.name,
            is_builtin=bool(s.is_builtin),
            curriculum_model=(
                s.curriculum_model.value if s.curriculum_model else None
            ),
            min_grade_level=s.min_grade_level,
            max_grade_level=s.max_grade_level,
            available_for_graduate=bool(s.available_for_graduate),
        )
        for s in subjects
    ]
    return SubjectListResponse(items=items)


@router.get(
    "/subjects/{subject_id}/topics",
    response_model=TopicListResponse,
)
def library_subject_topics_v2(
    subject_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    subj = db.query(Subject.id).filter(
        Subject.id == subject_id,
        or_(Subject.is_builtin.is_(True), Subject.teacher_id == user.id),
    ).first()
    if not subj:
        raise _not_found("subject_not_found", "Ders bulunamadı.")
    topics = _accessible_topics(db, subject_id, user.id)
    items = [
        TopicRef(
            id=t.id,
            name=t.name,
            subject_id=t.subject_id,
            is_builtin=bool(t.is_builtin),
            order=t.order,
        )
        for t in topics
    ]
    return TopicListResponse(items=items)


# =============================================================================
# Books — list / create / detail / patch / delete
# =============================================================================


@router.get("/books", response_model=BookListResponse)
def library_books_list_v2(
    q: str | None = Query(None, max_length=120),
    subject_id: int | None = Query(None),
    type: str | None = Query(None),
    grade_level: int | None = Query(None, ge=5, le=12),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Kitap listesi — filtreler (Jinja kart filtreleri ile aynı):
       - q: ad/yayınevi arama (case-insensitive contains)
       - subject_id: belirli ders
       - type: BookType.value
       - grade_level: hedef grade kapsama (target_grade_min..max ile overlap)
    """
    base = (
        db.query(Book)
        .options(
            joinedload(Book.subject),
            joinedload(Book.sections),
            joinedload(Book.student_books),
        )
        .filter(Book.teacher_id == user.id)
    )
    if subject_id is not None:
        base = base.filter(Book.subject_id == subject_id)
    if type:
        try:
            base = base.filter(Book.type == BookType(type))
        except ValueError:
            pass
    if q:
        like = f"%{q.strip().lower()}%"
        base = base.filter(
            or_(
                func.lower(Book.name).like(like),
                func.lower(func.coalesce(Book.publisher, "")).like(like),
            )
        )
    books = base.order_by(Book.created_at.desc()).all()
    if grade_level is not None:
        # Hedef aralığı belirtilmemiş kitap → tüm seviyeler eşleşir
        def in_range(b: Book) -> bool:
            if b.target_grade_min is None and b.target_grade_max is None:
                return True
            lo = b.target_grade_min or 5
            hi = b.target_grade_max or 12
            return lo <= grade_level <= hi
        books = [b for b in books if in_range(b)]
    return BookListResponse(
        items=[_build_book_list_item(b) for b in books],
        total=len(books),
    )


@router.post(
    "/books",
    response_model=MutationResponse[BookDetailResponse],
)
def library_book_create_v2(
    body: BookCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Yeni kitap. Opsiyonel `template_id` → şablonun section'ları kopyalanır."""
    name = (body.name or "").strip()
    if not name:
        raise _validation_error("name_required", "Kitap adı zorunlu.")
    try:
        book_type = BookType(body.type)
    except ValueError:
        raise _validation_error("invalid_type", "Geçersiz kitap tipi.")
    subj = db.query(Subject.id).filter(
        Subject.id == body.subject_id,
        or_(Subject.is_builtin.is_(True), Subject.teacher_id == user.id),
    ).first()
    if not subj:
        raise _validation_error("invalid_subject", "Ders bulunamadı veya erişiminiz yok.")

    g_min = body.target_grade_min
    g_max = body.target_grade_max
    if g_min is not None and not (4 <= g_min <= 12):
        g_min = None
    if g_max is not None and not (4 <= g_max <= 12):
        g_max = None
    if g_min is not None and g_max is not None and g_min > g_max:
        g_min, g_max = g_max, g_min

    template: BookTemplate | None = None
    if body.template_id is not None:
        template = _get_owned_template(db, body.template_id, user.id)

    book = Book(
        teacher_id=user.id,
        subject_id=body.subject_id,
        name=name,
        publisher=(body.publisher or "").strip() or None,
        type=book_type,
        avg_questions_per_test=body.avg_questions_per_test,
        target_grade_min=g_min,
        target_grade_max=g_max,
        target_graduate=bool(body.target_graduate),
    )
    db.add(book)
    db.flush()
    if template:
        for ts in template.sections:
            db.add(BookSection(
                book_id=book.id,
                label=ts.label,
                test_count=ts.default_test_count,
                order=ts.order,
            ))
    db.commit()
    db.refresh(book)
    return MutationResponse[BookDetailResponse](
        data=_build_book_detail(db, book),
        invalidate=_invalidate_book(user.id),
    )


@router.get("/books/{book_id}", response_model=BookDetailResponse)
def library_book_detail_v2(
    book_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    book = _get_owned_book(db, book_id, user.id)
    return _build_book_detail(db, book)


@router.patch(
    "/books/{book_id}",
    response_model=MutationResponse[BookDetailResponse],
)
def library_book_patch_v2(
    book_id: int,
    body: BookPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    book = _get_owned_book(db, book_id, user.id)
    if body.name is not None:
        nn = body.name.strip()
        if not nn:
            raise _validation_error("name_required", "Kitap adı boş olamaz.")
        book.name = nn
    if body.publisher is not None:
        book.publisher = body.publisher.strip() or None
    if body.type is not None:
        try:
            book.type = BookType(body.type)
        except ValueError:
            pass
    if body.subject_id is not None:
        subj = db.query(Subject.id).filter(
            Subject.id == body.subject_id,
            or_(Subject.is_builtin.is_(True), Subject.teacher_id == user.id),
        ).first()
        if not subj:
            raise _validation_error(
                "invalid_subject", "Ders bulunamadı veya erişiminiz yok.",
            )
        book.subject_id = body.subject_id
    if body.avg_questions_per_test is not None:
        book.avg_questions_per_test = body.avg_questions_per_test
    if body.target_grade_min is not None:
        v = body.target_grade_min
        book.target_grade_min = v if (4 <= v <= 12) else None
    if body.target_grade_max is not None:
        v = body.target_grade_max
        book.target_grade_max = v if (4 <= v <= 12) else None
    if (
        book.target_grade_min is not None
        and book.target_grade_max is not None
        and book.target_grade_min > book.target_grade_max
    ):
        book.target_grade_min, book.target_grade_max = (
            book.target_grade_max, book.target_grade_min,
        )
    if body.target_graduate is not None:
        book.target_graduate = bool(body.target_graduate)
    db.commit()
    db.refresh(book)
    return MutationResponse[BookDetailResponse](
        data=_build_book_detail(db, book),
        invalidate=_invalidate_book(user.id, book.id),
    )


@router.delete(
    "/books/{book_id}",
    response_model=MutationResponse[DeletedRef],
)
def library_book_delete_v2(
    book_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Kitabı sil — rezerv veya tamamlanan testi olan atamalar varsa 409."""
    book = _get_owned_book(db, book_id, user.id)
    # Atanmış öğrencilerin progress kontrolü
    has_progress = False
    for sb in book.student_books or []:
        for p in (sb.section_progress or []):
            if p.reserved_count > 0 or p.completed_count > 0:
                has_progress = True
                break
        if has_progress:
            break
    if has_progress:
        raise _conflict(
            "has_progress",
            "Kitapta ilerleme/rezerv var — silinemez. Önce öğrencilerin görevlerini boşalt.",
        )
    db.delete(book)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=book_id),
        invalidate=_invalidate_book(user.id, book_id),
    )


# =============================================================================
# Sections — create / bulk / patch / delete / clear-all
# =============================================================================


@router.post(
    "/books/{book_id}/sections",
    response_model=MutationResponse[BookSectionItem],
)
def library_section_create_v2(
    book_id: int,
    body: SectionCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    book = _get_owned_book(db, book_id, user.id)
    label = (body.label or "").strip()
    if not label:
        raise _validation_error("label_required", "Bölüm adı zorunlu.")
    if body.test_count < 1:
        raise _validation_error("invalid_test_count", "Test sayısı en az 1 olmalı.")
    if body.topic_id is not None:
        t = db.query(Topic.id).filter(
            Topic.id == body.topic_id,
            Topic.subject_id == book.subject_id,
            or_(Topic.is_builtin.is_(True), Topic.teacher_id == user.id),
        ).first()
        if not t:
            raise _validation_error("invalid_topic", "Konu bulunamadı.")
    max_order = max((s.order for s in book.sections or []), default=-1)
    section = BookSection(
        book_id=book.id,
        topic_id=body.topic_id,
        label=label,
        test_count=body.test_count,
        order=max_order + 1,
    )
    db.add(section)
    db.flush()
    for sb in book.student_books or []:
        db.add(SectionProgress(
            student_book_id=sb.id,
            book_section_id=section.id,
            reserved_count=0,
            completed_count=0,
        ))
    db.commit()
    db.refresh(section)
    return MutationResponse[BookSectionItem](
        data=_build_section_item(db, section),
        invalidate=_invalidate_book(user.id, book.id),
    )


@router.post(
    "/books/{book_id}/sections/bulk-from-catalog",
    response_model=MutationResponse[BulkCatalogResult],
)
def library_sections_bulk_v2(
    book_id: int,
    body: SectionsBulkFromCatalogBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Subject kataloğundan seçili topic'leri tek seferde ekle.

    Aynı topic'i zaten içeren section atlanır (`skipped_existing_count`).
    """
    book = _get_owned_book(db, book_id, user.id)
    if not body.items:
        raise _validation_error("no_topics", "En az bir konu seçin.")
    accessible_ids = {
        t.id for t in _accessible_topics(db, book.subject_id, user.id)
    }
    existing_topic_ids = {
        s.topic_id for s in (book.sections or []) if s.topic_id is not None
    }
    max_order = max((s.order for s in book.sections or []), default=-1)

    added = 0
    skipped = 0
    for it in body.items:
        if it.topic_id not in accessible_ids:
            continue
        if it.topic_id in existing_topic_ids:
            skipped += 1
            continue
        tc = it.test_count if it.test_count >= 1 else (book.avg_questions_per_test or 5)
        topic = db.query(Topic).filter(Topic.id == it.topic_id).first()
        if not topic:
            continue
        max_order += 1
        sec = BookSection(
            book_id=book.id,
            topic_id=it.topic_id,
            label=topic.name,
            test_count=tc,
            order=max_order,
        )
        db.add(sec)
        db.flush()
        for sb in book.student_books or []:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=sec.id,
                reserved_count=0,
                completed_count=0,
            ))
        added += 1
    db.commit()
    return MutationResponse[BulkCatalogResult](
        data=BulkCatalogResult(
            added_count=added,
            skipped_existing_count=skipped,
        ),
        invalidate=_invalidate_book(user.id, book.id),
    )


@router.patch(
    "/books/{book_id}/sections/{section_id}",
    response_model=MutationResponse[BookSectionItem],
)
def library_section_patch_v2(
    book_id: int,
    section_id: int,
    body: SectionPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    book = _get_owned_book(db, book_id, user.id)
    section = next((s for s in (book.sections or []) if s.id == section_id), None)
    if not section:
        raise _not_found("section_not_found", "Bölüm bulunamadı.")
    if body.label is not None:
        new_label = body.label.strip()
        if not new_label:
            raise _validation_error("label_required", "Bölüm adı boş olamaz.")
        section.label = new_label
    if body.topic_id is not None:
        t = db.query(Topic.id).filter(
            Topic.id == body.topic_id,
            Topic.subject_id == book.subject_id,
            or_(Topic.is_builtin.is_(True), Topic.teacher_id == user.id),
        ).first()
        if not t:
            raise _validation_error("invalid_topic", "Konu bulunamadı.")
        section.topic_id = body.topic_id
    if body.test_count is not None:
        if body.test_count < 1:
            raise _validation_error("invalid_test_count", "Test sayısı en az 1 olmalı.")
        # Test sayısı rezerv+tamam altına düşemez (her öğrenci için)
        rows = (
            db.query(SectionProgress)
            .filter(SectionProgress.book_section_id == section.id)
            .all()
        )
        min_required = max(
            (p.reserved_count + p.completed_count for p in rows), default=0,
        )
        if body.test_count < min_required:
            raise _validation_error(
                "invalid_section_count",
                f"Test sayısı {min_required}'dan az olamaz (mevcut rezerv+tamam).",
            )
        section.test_count = body.test_count
    db.commit()
    db.refresh(section)
    return MutationResponse[BookSectionItem](
        data=_build_section_item(db, section),
        invalidate=_invalidate_book(user.id, book.id),
    )


@router.delete(
    "/books/{book_id}/sections/{section_id}",
    response_model=MutationResponse[DeletedRef],
)
def library_section_delete_v2(
    book_id: int,
    section_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    book = _get_owned_book(db, book_id, user.id)
    section = next((s for s in (book.sections or []) if s.id == section_id), None)
    if not section:
        raise _not_found("section_not_found", "Bölüm bulunamadı.")
    reserved, completed = _section_progress_totals(db, section.id)
    if reserved > 0 or completed > 0:
        raise _conflict(
            "has_progress",
            "Bölümde rezerv/tamam test var — silinemez.",
            {"reserved": reserved, "completed": completed},
        )
    db.delete(section)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=section_id),
        invalidate=_invalidate_book(user.id, book.id),
    )


@router.post(
    "/books/{book_id}/clear-sections",
    response_model=MutationResponse[DeletedRef],
)
def library_clear_sections_v2(
    book_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Tüm bölümleri sil — herhangi birinde rezerv/tamam varsa 409."""
    book = _get_owned_book(db, book_id, user.id)
    section_ids = [s.id for s in (book.sections or [])]
    if not section_ids:
        return MutationResponse[DeletedRef](
            data=DeletedRef(deleted=True, id=book_id),
            invalidate=_invalidate_book(user.id, book.id),
        )
    row = (
        db.query(
            func.coalesce(func.sum(SectionProgress.reserved_count), 0),
            func.coalesce(func.sum(SectionProgress.completed_count), 0),
        )
        .filter(SectionProgress.book_section_id.in_(section_ids))
        .first()
    )
    reserved = int(row[0] or 0) if row else 0
    completed = int(row[1] or 0) if row else 0
    if reserved > 0 or completed > 0:
        raise _conflict(
            "has_progress",
            "Bölümlerde rezerv/tamam test var — temizlenemez.",
            {"reserved": reserved, "completed": completed},
        )
    for s in list(book.sections or []):
        db.delete(s)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=book_id),
        invalidate=_invalidate_book(user.id, book.id),
    )


# =============================================================================
# AI suggest
# =============================================================================


@router.post(
    "/books/{book_id}/ai-suggest",
    response_model=MutationResponse[AiSuggestResult],
)
def library_ai_suggest_v2(
    book_id: int,
    body: AiSuggestBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """AI'dan ünite önerisi al + kitaba ekle + draft şablon olarak kaydet.

    Önkoşul: mevcut sections boş olmalı (rezerv güvenliği). Plan/feature flag/
    kredi kontrolü mevcut Jinja akışıyla birebir.
    """
    from app.models import UsageKind
    from app.models.book import BOOK_TYPE_LABELS
    from app.services.ai_book_template import (
        AIInvalidResponse,
        AIServiceUnavailable,
        suggest_sections,
    )
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits
    from app.services.feature_flags import is_enabled

    book = _get_owned_book(db, book_id, user.id)
    if book.sections:
        raise _conflict(
            "sections_exist",
            "Mevcut üniteler var — önce 'Sıfırdan başla' ile temizleyin.",
        )
    if not is_enabled(db, "ai_book_template", institution=user.institution):
        raise _validation_error(
            "ai_disabled_for_plan",
            "AI ünite önerisi şu an kapalı (sistem yöneticisi).",
        )

    grade_label = (body.grade_hint or "").strip()
    if not grade_label:
        if book.target_grade_min and book.target_grade_max:
            if book.target_grade_min == book.target_grade_max:
                grade_label = f"{book.target_grade_min}. sınıf"
            else:
                grade_label = (
                    f"{book.target_grade_min}-{book.target_grade_max}. sınıf"
                )
        elif book.target_graduate:
            grade_label = "Mezun (YKS)"
        else:
            grade_label = "belirtilmemiş"

    owner = CreditOwner.for_user(user)
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_BOOK_TEMPLATE,
            actor_user_id=user.id, autocommit=False,
        ) as ctx:
            suggestions = suggest_sections(
                book_name=book.name,
                publisher=book.publisher,
                subject_name=book.subject.name if book.subject else "",
                book_type_label=BOOK_TYPE_LABELS.get(book.type, book.type.value),
                grade_label=grade_label,
            )
            ctx.set_metadata({
                "book_id": book.id,
                "subject": book.subject.name if book.subject else None,
            })
    except CreditBlocked as e:
        db.rollback()
        raise _validation_error("ai_credit_exhausted", f"Kredi sınırı: {e.message}")
    except AIServiceUnavailable as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "upstream_unavailable",
                "code": "ai_provider_error",
                "message": f"AI servisi kullanılamıyor: {e}",
            },
        )
    except AIInvalidResponse as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "upstream_unavailable",
                "code": "ai_provider_error",
                "message": f"AI yanıtı parse edilemedi: {e}",
            },
        )

    # Sections'ları kitaba ekle
    new_sections: list[BookSection] = []
    for i, sec in enumerate(suggestions):
        new_sec = BookSection(
            book_id=book.id,
            label=sec["label"],
            test_count=sec["default_test_count"],
            order=i,
        )
        db.add(new_sec)
        db.flush()
        for sb in book.student_books or []:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=new_sec.id,
                reserved_count=0,
                completed_count=0,
            ))
        new_sections.append(new_sec)

    # Draft template
    tpl = BookTemplate(
        teacher_id=user.id,
        name=book.name,
        publisher=book.publisher,
        type=book.type,
        subject_id=book.subject_id,
        target_grade_min=book.target_grade_min,
        target_grade_max=book.target_grade_max,
        target_graduate=bool(book.target_graduate),
        avg_questions_per_test=book.avg_questions_per_test,
        is_ai_generated=True,
        is_verified=False,
    )
    db.add(tpl)
    db.flush()
    for i, sec in enumerate(suggestions):
        db.add(BookTemplateSection(
            template_id=tpl.id,
            label=sec["label"],
            default_test_count=sec["default_test_count"],
            order=i,
        ))
    db.commit()
    for s in new_sections:
        db.refresh(s)

    return MutationResponse[AiSuggestResult](
        data=AiSuggestResult(
            added_section_count=len(new_sections),
            template_id=tpl.id,
            suggestions=[_build_section_item(db, s) for s in new_sections],
        ),
        invalidate=_invalidate_book(user.id, book.id),
    )


# =============================================================================
# Assignments
# =============================================================================


@router.patch(
    "/books/{book_id}/assignments",
    response_model=MutationResponse[AssignmentsResult],
)
def library_book_assignments_v2(
    book_id: int,
    body: AssignmentsPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Atamaları senkronla (diff):
       - Eksik öğrenciler atanır
       - Hedef listede olmayan ve rezervi olmayanlar silinir
       - Rezerv olan ataması korunur, ID'leri `skipped_with_progress`'de döner
    """
    book = _get_owned_book(db, book_id, user.id)
    target_ids = {int(x) for x in body.student_ids if x is not None}

    valid_ids = {
        u.id for u in db.query(User).filter(
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
            User.id.in_(target_ids) if target_ids else False,
        ).all()
    } if target_ids else set()

    existing_by_sid: dict[int, StudentBook] = {
        sb.student_id: sb for sb in (book.student_books or [])
    }

    affected_student_ids: list[int] = []
    assigned_count = 0
    for sid in valid_ids:
        if sid in existing_by_sid:
            continue
        sb = StudentBook(student_id=sid, book_id=book.id)
        db.add(sb)
        db.flush()
        for sec in (book.sections or []):
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=sec.id,
                reserved_count=0,
                completed_count=0,
            ))
        assigned_count += 1
        affected_student_ids.append(sid)

    removed_count = 0
    skipped: list[int] = []
    for sid, sb in list(existing_by_sid.items()):
        if sid in valid_ids:
            continue
        has_progress = any(
            (p.reserved_count > 0 or p.completed_count > 0)
            for p in (sb.section_progress or [])
        )
        if has_progress:
            skipped.append(sid)
            continue
        db.delete(sb)
        removed_count += 1
        affected_student_ids.append(sid)

    db.commit()
    return MutationResponse[AssignmentsResult](
        data=AssignmentsResult(
            assigned_count=assigned_count,
            removed_count=removed_count,
            skipped_with_progress=skipped,
        ),
        invalidate=_invalidate_assignments(user.id, book.id, affected_student_ids),
    )


# =============================================================================
# Templates
# =============================================================================


@router.get("/templates", response_model=BookTemplateListResponse)
def library_templates_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    tpls = (
        db.query(BookTemplate)
        .options(joinedload(BookTemplate.sections))
        .filter(BookTemplate.teacher_id == user.id)
        .order_by(BookTemplate.created_at.desc())
        .all()
    )
    return BookTemplateListResponse(
        items=[_build_template_item(db, t) for t in tpls],
        total=len(tpls),
    )


@router.post(
    "/books/{book_id}/save-as-template",
    response_model=MutationResponse[BookTemplateListItem],
)
def library_save_as_template_v2(
    book_id: int,
    body: SaveAsTemplateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    book = _get_owned_book(db, book_id, user.id)
    if not book.sections:
        raise _validation_error(
            "no_sections",
            "Şablon olarak kaydetmek için önce ünite ekleyin.",
        )
    name = (body.template_name or "").strip() or book.name
    tpl = BookTemplate(
        teacher_id=user.id,
        name=name,
        publisher=book.publisher,
        type=book.type,
        subject_id=book.subject_id,
        target_grade_min=book.target_grade_min,
        target_grade_max=book.target_grade_max,
        target_graduate=bool(book.target_graduate),
        avg_questions_per_test=book.avg_questions_per_test,
        is_ai_generated=False,
        is_verified=True,
    )
    db.add(tpl)
    db.flush()
    for s in (book.sections or []):
        db.add(BookTemplateSection(
            template_id=tpl.id,
            label=s.label,
            default_test_count=s.test_count,
            order=s.order,
        ))
    db.commit()
    db.refresh(tpl)
    return MutationResponse[BookTemplateListItem](
        data=_build_template_item(db, tpl),
        invalidate=_invalidate_book(user.id, book.id),
    )


@router.post(
    "/books/{book_id}/apply-template",
    response_model=MutationResponse[ApplyTemplateResult],
)
def library_apply_template_v2(
    book_id: int,
    body: ApplyTemplateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    book = _get_owned_book(db, book_id, user.id)
    tpl = _get_owned_template(db, body.template_id, user.id)

    if body.overwrite:
        # Rezerv kontrol
        section_ids = [s.id for s in book.sections or []]
        if section_ids:
            row = (
                db.query(
                    func.coalesce(func.sum(SectionProgress.reserved_count), 0),
                    func.coalesce(func.sum(SectionProgress.completed_count), 0),
                )
                .filter(SectionProgress.book_section_id.in_(section_ids))
                .first()
            )
            reserved = int(row[0] or 0) if row else 0
            completed = int(row[1] or 0) if row else 0
            if reserved > 0 or completed > 0:
                raise _conflict(
                    "has_progress",
                    "Üzerine yazma yapılamıyor: bazı ünitelerde rezerv/tamam test var.",
                    {"reserved": reserved, "completed": completed},
                )
        for s in list(book.sections or []):
            db.delete(s)
        db.flush()

    # Mevcut label seti — duplicate önle
    existing_labels = {s.label.strip().lower() for s in (book.sections or [])}
    max_order = max((s.order for s in book.sections or []), default=-1)
    added = 0
    for ts in (tpl.sections or []):
        if ts.label.strip().lower() in existing_labels:
            continue
        max_order += 1
        sec = BookSection(
            book_id=book.id,
            label=ts.label,
            test_count=ts.default_test_count,
            order=max_order,
        )
        db.add(sec)
        db.flush()
        for sb in book.student_books or []:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=sec.id,
                reserved_count=0,
                completed_count=0,
            ))
        added += 1
    db.commit()
    return MutationResponse[ApplyTemplateResult](
        data=ApplyTemplateResult(added_count=added, overwrote=bool(body.overwrite)),
        invalidate=_invalidate_book(user.id, book.id),
    )


@router.delete(
    "/templates/{template_id}",
    response_model=MutationResponse[DeletedRef],
)
def library_template_delete_v2(
    template_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    tpl = _get_owned_template(db, template_id, user.id)
    db.delete(tpl)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=template_id),
        invalidate=_invalidate_book(user.id),
    )


@router.post(
    "/templates/{template_id}/verify",
    response_model=MutationResponse[BookTemplateListItem],
)
def library_template_verify_v2(
    template_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """AI-generated draft şablonu kullanıcı tarafından doğrulanmış işaretle."""
    tpl = _get_owned_template(db, template_id, user.id)
    tpl.is_verified = True
    db.commit()
    db.refresh(tpl)
    return MutationResponse[BookTemplateListItem](
        data=_build_template_item(db, tpl),
        invalidate=_invalidate_book(user.id),
    )


# =============================================================================
# Book sets
# =============================================================================


def _grade_label_tr(grade_level: int | None, is_graduate: bool) -> str:
    if is_graduate:
        return "Mezun"
    if grade_level is None:
        return "—"
    return f"{grade_level}. sınıf"


def _set_target_grade_label_tr(
    target_min: int | None, target_max: int | None, target_graduate: bool,
) -> str:
    """Set'in hedef sınıf aralığı için kısa, okunabilir etiket.

    Örnek çıktılar:
      - "5-8. sınıf" / "Lise (9-12)" / "11. sınıf"
      - "Mezun" (yalnız mezun)
      - "Lise + Mezun" (lise aralığı + mezun)
      - "Tüm seviyeler" (üç alan da boş/false)
    """
    parts: list[str] = []
    if target_min is not None and target_max is not None:
        if target_min == target_max:
            parts.append(f"{target_min}. sınıf")
        elif target_min == 5 and target_max == 8:
            parts.append("5-8. sınıf")
        elif target_min == 9 and target_max == 12:
            parts.append("Lise (9-12)")
        else:
            parts.append(f"{target_min}-{target_max}. sınıf")
    elif target_min is not None:
        parts.append(f"{target_min}+ sınıf")
    elif target_max is not None:
        parts.append(f"≤{target_max}. sınıf")
    if target_graduate:
        parts.append("Mezun")
    if not parts:
        return "Tüm seviyeler"
    return " · ".join(parts)


def _validate_target_grade(
    target_min: int | None, target_max: int | None,
) -> None:
    """Min ≤ Max + 4-12 aralığı doğrulaması."""
    if target_min is not None and (target_min < 4 or target_min > 12):
        raise _validation_error(
            "invalid_target_grade_min",
            "Min sınıf 4-12 aralığında olmalı.",
        )
    if target_max is not None and (target_max < 4 or target_max > 12):
        raise _validation_error(
            "invalid_target_grade_max",
            "Maks sınıf 4-12 aralığında olmalı.",
        )
    if (
        target_min is not None
        and target_max is not None
        and target_min > target_max
    ):
        raise _validation_error(
            "invalid_target_grade_range",
            "Min sınıf maks sınıftan büyük olamaz.",
        )


def _grade_distribution_from_students(
    rows: list[tuple[int | None, bool, int]],
) -> list[BookSetGradeBucket]:
    """`rows` her satırı (grade_level, is_graduate, student_count). Sıralama:
    önce sınıflar 5→12, ardından mezunlar, son olarak diğerleri (None)."""
    buckets: list[BookSetGradeBucket] = []
    for grade, is_grad, count in rows:
        if count <= 0:
            continue
        buckets.append(
            BookSetGradeBucket(
                grade_level=grade,
                is_graduate=is_grad,
                label_tr=_grade_label_tr(grade, is_grad),
                student_count=count,
            )
        )
    # Ortalama 13 satırlık tablo — Python sort yeterli.
    def key(b: BookSetGradeBucket) -> tuple[int, int]:
        if b.is_graduate:
            return (1, 0)
        if b.grade_level is None:
            return (2, 0)
        return (0, b.grade_level)
    buckets.sort(key=key)
    return buckets


def _book_set_student_aggregations(
    db: Session, sets: list[BookSet],
) -> dict[int, tuple[int, list[BookSetGradeBucket], list[BookSetAssignedStudent]]]:
    """Birden çok set için tek SQL'de öğrenci/grade/atanan-kitap-sayısı agregasyonu.

    Dönen sözlük: set_id → (student_count, grade_distribution, assigned_students).
    `assigned_students` listesi sınıfa göre artan, sonra ad'a göre sıralanır.
    """
    if not sets:
        return {}
    # Set → kitap id'leri
    set_to_book_ids: dict[int, list[int]] = {}
    book_to_sets: dict[int, list[int]] = {}
    for s in sets:
        bids = [it.book_id for it in (s.items or [])]
        set_to_book_ids[s.id] = bids
        for bid in bids:
            book_to_sets.setdefault(bid, []).append(s.id)
    all_book_ids = list({bid for bids in set_to_book_ids.values() for bid in bids})

    if not all_book_ids:
        return {
            s.id: (0, [], []) for s in sets
        }

    # Setteki kitaplardan en az birine atanmış (book_id, student_id) çiftleri
    rows = (
        db.query(StudentBook.book_id, StudentBook.student_id)
        .filter(StudentBook.book_id.in_(all_book_ids))
        .all()
    )
    student_ids = {sid for (_, sid) in rows}

    # Öğrencileri tek seferde çek (yalnız teacher tarafına ait olanlar zaten
    # StudentBook→Book→teacher_id ilişkisinden geliyor; ekstra filtre gereksiz).
    students = (
        db.query(User)
        .filter(User.id.in_(student_ids))
        .all()
    ) if student_ids else []
    student_by_id = {st.id: st for st in students}

    # Per-set agregasyonu
    out: dict[int, tuple[int, list[BookSetGradeBucket], list[BookSetAssignedStudent]]] = {}
    for s in sets:
        bids = set(set_to_book_ids.get(s.id, []))
        if not bids:
            out[s.id] = (0, [], [])
            continue
        # Bu setin kitaplarına atanmış (book_id, student_id) → set
        per_student_books: dict[int, set[int]] = {}
        for bid, sid in rows:
            if bid in bids:
                per_student_books.setdefault(sid, set()).add(bid)

        grade_counter: dict[tuple[int | None, bool], int] = {}
        assigned: list[BookSetAssignedStudent] = []
        for sid, book_set in per_student_books.items():
            st = student_by_id.get(sid)
            if st is None:
                continue
            grade = st.grade_level
            is_grad = bool(getattr(st, "is_graduate", False))
            grade_counter[(grade, is_grad)] = grade_counter.get((grade, is_grad), 0) + 1
            assigned.append(BookSetAssignedStudent(
                student_id=st.id,
                full_name=st.full_name,
                grade_level=grade,
                is_graduate=is_grad,
                is_active=bool(st.is_active),
                grade_label_tr=_grade_label_tr(grade, is_grad),
                assigned_book_count=len(book_set),
            ))

        # Sınıf → ad
        def sort_key(a: BookSetAssignedStudent) -> tuple[int, int, str]:
            if a.is_graduate:
                bucket = 99
            elif a.grade_level is None:
                bucket = 100
            else:
                bucket = a.grade_level
            return (0 if a.is_active else 1, bucket, a.full_name.lower())
        assigned.sort(key=sort_key)

        grade_rows = [(g, is_g, c) for (g, is_g), c in grade_counter.items()]
        out[s.id] = (
            len(per_student_books),
            _grade_distribution_from_students(grade_rows),
            assigned,
        )
    return out


def _build_set_detail(
    bs: BookSet,
    grade_distribution: list[BookSetGradeBucket] | None = None,
    assigned_students: list[BookSetAssignedStudent] | None = None,
) -> BookSetDetailResponse:
    items: list[BookSetMemberRef] = []
    for it in (bs.items or []):
        b = it.book
        items.append(BookSetMemberRef(
            book_id=it.book_id,
            book_name=b.name if b else "—",
            book_type=(b.type.value if b and b.type else "soru_bankasi"),
            subject_id=b.subject_id if b else 0,
            subject_name=b.subject.name if b and b.subject else None,
            order=it.order,
        ))
    return BookSetDetailResponse(
        id=bs.id,
        name=bs.name,
        notes=bs.notes,
        items=items,
        assigned_students=assigned_students or [],
        grade_distribution=grade_distribution or [],
        target_grade_min=bs.target_grade_min,
        target_grade_max=bs.target_grade_max,
        target_graduate=bool(bs.target_graduate),
        target_grade_label_tr=_set_target_grade_label_tr(
            bs.target_grade_min, bs.target_grade_max, bool(bs.target_graduate),
        ),
        created_at=bs.created_at,
    )


@router.get("/book-sets", response_model=BookSetListResponse)
def library_book_sets_list_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    sets = (
        db.query(BookSet)
        .options(joinedload(BookSet.items))
        .filter(BookSet.teacher_id == user.id)
        .order_by(BookSet.created_at.desc())
        .all()
    )
    agg = _book_set_student_aggregations(db, sets)
    items = [
        BookSetListItem(
            id=s.id,
            name=s.name,
            notes=s.notes,
            book_count=len(s.items or []),
            student_count=agg.get(s.id, (0, [], []))[0],
            grade_distribution=agg.get(s.id, (0, [], []))[1],
            target_grade_min=s.target_grade_min,
            target_grade_max=s.target_grade_max,
            target_graduate=bool(s.target_graduate),
            target_grade_label_tr=_set_target_grade_label_tr(
                s.target_grade_min, s.target_grade_max, bool(s.target_graduate),
            ),
            created_at=s.created_at,
        )
        for s in sets
    ]
    return BookSetListResponse(items=items, total=len(items))


@router.post(
    "/book-sets",
    response_model=MutationResponse[BookSetDetailResponse],
)
def library_book_set_create_v2(
    body: BookSetCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    name = (body.name or "").strip()
    if not name:
        raise _validation_error("name_required", "Set adı zorunlu.")
    _validate_target_grade(body.target_grade_min, body.target_grade_max)
    bs = BookSet(
        teacher_id=user.id,
        name=name,
        notes=(body.notes or "").strip() or None,
        target_grade_min=body.target_grade_min,
        target_grade_max=body.target_grade_max,
        target_graduate=bool(body.target_graduate),
    )
    db.add(bs)
    db.commit()
    db.refresh(bs)
    return MutationResponse[BookSetDetailResponse](
        data=_build_set_detail(bs),
        invalidate=_invalidate_set(user.id),
    )


def _detail_with_aggregation(db: Session, bs: BookSet) -> BookSetDetailResponse:
    _, grade_dist, assigned = _book_set_student_aggregations(db, [bs]).get(
        bs.id, (0, [], []),
    )
    return _build_set_detail(bs, grade_distribution=grade_dist, assigned_students=assigned)


@router.get(
    "/book-sets/{set_id}",
    response_model=BookSetDetailResponse,
)
def library_book_set_detail_v2(
    set_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    bs = _get_owned_book_set(db, set_id, user.id)
    return _detail_with_aggregation(db, bs)


@router.patch(
    "/book-sets/{set_id}",
    response_model=MutationResponse[BookSetDetailResponse],
)
def library_book_set_patch_v2(
    set_id: int,
    body: BookSetPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    bs = _get_owned_book_set(db, set_id, user.id)
    if body.name is not None:
        nn = body.name.strip()
        if not nn:
            raise _validation_error("name_required", "Set adı boş olamaz.")
        bs.name = nn
    if body.notes is not None:
        bs.notes = body.notes.strip() or None
    if body.clear_target_grade:
        bs.target_grade_min = None
        bs.target_grade_max = None
        bs.target_graduate = False
    else:
        new_min = (
            body.target_grade_min
            if body.target_grade_min is not None
            else bs.target_grade_min
        )
        new_max = (
            body.target_grade_max
            if body.target_grade_max is not None
            else bs.target_grade_max
        )
        _validate_target_grade(new_min, new_max)
        if body.target_grade_min is not None:
            bs.target_grade_min = body.target_grade_min
        if body.target_grade_max is not None:
            bs.target_grade_max = body.target_grade_max
        if body.target_graduate is not None:
            bs.target_graduate = bool(body.target_graduate)
    db.commit()
    db.refresh(bs)
    return MutationResponse[BookSetDetailResponse](
        data=_detail_with_aggregation(db, bs),
        invalidate=_invalidate_set(user.id, bs.id),
    )


@router.delete(
    "/book-sets/{set_id}",
    response_model=MutationResponse[DeletedRef],
)
def library_book_set_delete_v2(
    set_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    bs = _get_owned_book_set(db, set_id, user.id)
    db.delete(bs)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=set_id),
        invalidate=_invalidate_set(user.id, set_id),
    )


@router.post(
    "/book-sets/{set_id}/books",
    response_model=MutationResponse[AddBooksToSetResult],
)
def library_book_set_add_books_v2(
    set_id: int,
    body: AddBooksToSetBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    bs = _get_owned_book_set(db, set_id, user.id)
    if not body.book_ids:
        return MutationResponse[AddBooksToSetResult](
            data=AddBooksToSetResult(added_count=0, skipped_existing_count=0),
            invalidate=_invalidate_set(user.id, bs.id),
        )
    valid = {
        b.id for b in db.query(Book).filter(
            Book.teacher_id == user.id,
            Book.id.in_(body.book_ids),
        ).all()
    }
    existing = {it.book_id for it in (bs.items or [])}
    max_order = max((it.order for it in (bs.items or [])), default=-1)
    seen_in_request: set[int] = set()
    added = 0
    skipped = 0
    for bid in body.book_ids:
        if bid not in valid:
            continue
        if bid in existing or bid in seen_in_request:
            skipped += 1
            continue
        max_order += 1
        db.add(BookSetItem(set_id=bs.id, book_id=bid, order=max_order))
        seen_in_request.add(bid)
        added += 1
    db.commit()
    return MutationResponse[AddBooksToSetResult](
        data=AddBooksToSetResult(added_count=added, skipped_existing_count=skipped),
        invalidate=_invalidate_set(user.id, bs.id),
    )


@router.delete(
    "/book-sets/{set_id}/books/{book_id}",
    response_model=MutationResponse[DeletedRef],
)
def library_book_set_remove_book_v2(
    set_id: int,
    book_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    bs = _get_owned_book_set(db, set_id, user.id)
    item = next((it for it in (bs.items or []) if it.book_id == book_id), None)
    if not item:
        raise _not_found(
            "book_set_item_not_found",
            "Kitap bu sette değil.",
        )
    db.delete(item)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=book_id),
        invalidate=_invalidate_set(user.id, bs.id),
    )


# Marker for `datetime` use in models — keeps import alive if all paths refactor.
__used_datetime = datetime.now(timezone.utc)
