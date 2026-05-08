from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import (
    Book,
    BookSection,
    BookSet,
    BookSetItem,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.templating import templates

router = APIRouter(prefix="/teacher/books")


def _accessible_subjects(db: Session, teacher_id: int) -> list[Subject]:
    # built-in (shared) + teacher's own
    return (
        db.query(Subject)
        .filter((Subject.is_builtin.is_(True)) | (Subject.teacher_id == teacher_id))
        .order_by(Subject.order, Subject.name)
        .all()
    )


def _accessible_topics(db: Session, subject_id: int, teacher_id: int) -> list[Topic]:
    return (
        db.query(Topic)
        .filter(
            Topic.subject_id == subject_id,
            (Topic.is_builtin.is_(True)) | (Topic.teacher_id == teacher_id),
        )
        .order_by(Topic.order, Topic.name)
        .all()
    )


@router.get("")
def list_books(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    books = (
        db.query(Book)
        .options(joinedload(Book.subject), joinedload(Book.sections))
        .filter(Book.teacher_id == user.id)
        .order_by(Book.created_at.desc())
        .all()
    )
    subjects = _accessible_subjects(db, user.id)

    # Ders bazlı gruplandırma + ders/tip/sınıf sayımları (chip filtreler ve sticky
    # bölüm başlıkları için).
    books_by_subject: dict[int, dict] = {}
    for s in subjects:
        books_by_subject[s.id] = {
            "subject": s,
            "books": [],
            "total_sections": 0,
            "total_tests": 0,
        }
    type_counts: dict[str, int] = {bt.value: 0 for bt in BookType}
    # Sınıf-bazlı kitap sayımı (chip için): bir kitap kapsadığı her seviye
    # için birer kez sayılır. "graduate" özel anahtar mezunu temsil eder.
    grade_counts: dict[str, int] = {str(g): 0 for g in range(5, 13)}
    grade_counts["graduate"] = 0

    for book in books:
        bucket = books_by_subject.get(book.subject_id)
        if bucket is None:
            # Subject erişilebilir değilse de göstereceğiz — virtual bucket
            bucket = {
                "subject": book.subject,
                "books": [],
                "total_sections": 0,
                "total_tests": 0,
            }
            books_by_subject[book.subject_id] = bucket
        bucket["books"].append(book)
        bucket["total_sections"] += len(book.sections)
        bucket["total_tests"] += book.total_tests
        type_counts[book.type.value] = type_counts.get(book.type.value, 0) + 1

        # Sınıf sayımları — kitabın hedef aralığına göre her grade için say
        lo = book.target_grade_min
        hi = book.target_grade_max
        if lo is None and hi is None and not book.target_graduate:
            # Hedef belirtilmemiş kitap — tüm seviyelere uygun varsayılır,
            # her grade'e + ekle (filtrede tüm chip'lere eşleşir).
            for g in range(5, 13):
                grade_counts[str(g)] = grade_counts[str(g)] + 1
        else:
            if lo is not None or hi is not None:
                lo_eff = lo if lo is not None else 5
                hi_eff = hi if hi is not None else 12
                for g in range(max(5, lo_eff), min(12, hi_eff) + 1):
                    grade_counts[str(g)] = grade_counts[str(g)] + 1
            if book.target_graduate:
                grade_counts["graduate"] = grade_counts["graduate"] + 1

    # Sadece kitabı olan dersleri sırala (ders order, name)
    grouped = sorted(
        [v for v in books_by_subject.values() if v["books"]],
        key=lambda g: (g["subject"].order, g["subject"].name),
    )

    overall = {
        "books": len(books),
        "sections": sum(len(b.sections) for b in books),
        "tests": sum(b.total_tests for b in books),
    }

    # Form dropdown'u için subjects'i müfredat modeli bazında grupla
    # (aynı ders adı farklı modellerde ayrı kayıt — optgroup ile ayrılır).
    from app.models import CurriculumModel
    MODEL_LABELS = {
        CurriculumModel.LGS: "LGS Müfredatı (5-8)",
        CurriculumModel.MAARIF_LISE: "Maarif Modeli (9-12)",
        CurriculumModel.KLASIK_LISE: "Klasik Lise (11-12, son nesil)",
    }
    MODEL_ORDER = [CurriculumModel.LGS, CurriculumModel.MAARIF_LISE, CurriculumModel.KLASIK_LISE]
    subjects_grouped: list[dict] = []
    seen_models: dict = {}
    for s in subjects:
        key = s.curriculum_model
        if key not in seen_models:
            seen_models[key] = []
        seen_models[key].append(s)
    # NULL (model belirtilmemiş) ders varsa "Diğer" başlığı altında en sona
    for cm in MODEL_ORDER:
        if cm in seen_models and seen_models[cm]:
            subjects_grouped.append({
                "label": MODEL_LABELS[cm],
                "subjects": seen_models[cm],
            })
    if None in seen_models and seen_models[None]:
        subjects_grouped.append({
            "label": "Diğer / Sınıflandırılmamış",
            "subjects": seen_models[None],
        })

    return templates.TemplateResponse(
        "teacher/books_list.html",
        {
            "request": request,
            "user": user,
            "books": books,
            "subjects": subjects,
            "subjects_grouped": subjects_grouped,
            "BookType": BookType,
            "grouped": grouped,
            "type_counts": type_counts,
            "grade_counts": grade_counts,
            "overall": overall,
        },
    )


@router.post("")
def create_book(
    name: str = Form(...),
    publisher: str = Form(""),
    subject_id: int = Form(...),
    type: str = Form(...),
    avg_questions_per_test: str = Form(""),
    target_grade_min: str = Form(""),
    target_grade_max: str = Form(""),
    target_graduate: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        book_type = BookType(type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz kitap tipi")
    avg_q: int | None = None
    if avg_questions_per_test.strip():
        try:
            avg_q = int(avg_questions_per_test)
        except ValueError:
            avg_q = None

    # Hedef sınıf aralığı — boş bırakılabilir (her seviyeye uygun)
    def _parse_grade(s: str) -> int | None:
        s = (s or "").strip()
        if not s:
            return None
        try:
            v = int(s)
            return v if 4 <= v <= 12 else None
        except ValueError:
            return None

    g_min = _parse_grade(target_grade_min)
    g_max = _parse_grade(target_grade_max)
    # min > max ise normalize et (kullanıcı yanlış girmiş olabilir)
    if g_min is not None and g_max is not None and g_min > g_max:
        g_min, g_max = g_max, g_min

    is_for_graduate = target_graduate.strip().lower() in ("on", "1", "true", "yes")

    book = Book(
        teacher_id=user.id,
        subject_id=subject_id,
        name=name.strip(),
        publisher=publisher.strip() or None,
        type=book_type,
        avg_questions_per_test=avg_q,
        target_grade_min=g_min,
        target_grade_max=g_max,
        target_graduate=is_for_graduate,
    )
    db.add(book)
    db.commit()
    return RedirectResponse(url=f"/teacher/books/{book.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{book_id}")
def book_detail(
    book_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = (
        db.query(Book)
        .options(joinedload(Book.sections).joinedload(BookSection.topic), joinedload(Book.subject))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    topics = _accessible_topics(db, book.subject_id, user.id)
    all_students = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    assigned_student_ids = {sb.student_id for sb in book.student_books}
    return templates.TemplateResponse(
        "teacher/book_detail.html",
        {
            "request": request,
            "user": user,
            "book": book,
            "topics": topics,
            "students": all_students,
            "assigned_ids": assigned_student_ids,
        },
    )


@router.post("/{book_id}/sections")
def add_section(
    book_id: int,
    label: str = Form(...),
    topic_id: str = Form(""),
    test_count: int = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.id == book_id, Book.teacher_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    if test_count < 1:
        raise HTTPException(status_code=400, detail="Test sayısı en az 1 olmalı")
    parsed_topic_id: int | None = None
    if topic_id.strip():
        try:
            parsed_topic_id = int(topic_id)
        except ValueError:
            parsed_topic_id = None
    max_order = max((s.order for s in book.sections), default=-1)
    section = BookSection(
        book_id=book.id,
        topic_id=parsed_topic_id,
        label=label.strip(),
        test_count=test_count,
        order=max_order + 1,
    )
    db.add(section)
    db.flush()
    # Atanmış öğrencilere de bu ünite için progress kaydı aç
    for sb in book.student_books:
        db.add(SectionProgress(
            student_book_id=sb.id,
            book_section_id=section.id,
            reserved_count=0,
            completed_count=0,
        ))
    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/sections/{section_id}/edit")
def edit_section(
    book_id: int,
    section_id: int,
    label: str = Form(...),
    test_count: int = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    section = (
        db.query(BookSection)
        .join(Book)
        .filter(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
            Book.teacher_id == user.id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404)
    # Test sayısı azaltılırsa rezerv+tamamlanan'ın altına düşmesin
    progresses = (
        db.query(SectionProgress).filter(SectionProgress.book_section_id == section.id).all()
    )
    min_required = max((p.reserved_count + p.completed_count for p in progresses), default=0)
    if test_count < min_required:
        raise HTTPException(
            status_code=400,
            detail=f"Test sayısı {min_required}'dan az olamaz (rezerv+çözülen).",
        )
    section.label = label.strip()
    section.test_count = test_count
    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/sections/{section_id}/delete")
def delete_section(
    book_id: int,
    section_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    section = (
        db.query(BookSection)
        .join(Book)
        .filter(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
            Book.teacher_id == user.id,
        )
        .first()
    )
    if section:
        db.delete(section)
        db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/assign")
async def assign_students(
    book_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404)

    form = await request.form()
    selected_ids: set[int] = set()
    for v in form.getlist("student_ids"):
        try:
            selected_ids.add(int(v))
        except (TypeError, ValueError):
            pass

    if selected_ids:
        valid_ids = {
            u.id for u in db.query(User).filter(
                User.teacher_id == user.id,
                User.role == UserRole.STUDENT,
                User.id.in_(selected_ids),
            ).all()
        }
    else:
        valid_ids = set()

    existing_sb = {
        sb.student_id: sb for sb in db.query(StudentBook)
        .filter(StudentBook.book_id == book.id).all()
    }

    # Yeni atamalar
    for sid in valid_ids:
        if sid in existing_sb:
            continue
        sb = StudentBook(student_id=sid, book_id=book.id)
        db.add(sb)
        db.flush()
        for section in book.sections:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=section.id,
                reserved_count=0,
                completed_count=0,
            ))

    # Artık seçili değilse sil (rezerv/tamamlanan varsa uyarı vermeden silme — basit MVP)
    for sid, sb in existing_sb.items():
        if sid not in valid_ids:
            # Güvenli: yalnızca hiç ilerleme yoksa sil
            has_progress = any(
                p.reserved_count > 0 or p.completed_count > 0 for p in sb.section_progress
            )
            if not has_progress:
                db.delete(sb)

    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/delete")
def delete_book(
    book_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.id == book_id, Book.teacher_id == user.id).first()
    if book:
        db.delete(book)
        db.commit()
    return RedirectResponse(url="/teacher/books", status_code=status.HTTP_303_SEE_OTHER)
