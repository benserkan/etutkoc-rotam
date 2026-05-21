import logging
from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
from starlette import status

from app.deps import get_db, require_teacher
from app.models import (
    Book,
    BookSection,
    BookSet,
    BookSetItem,
    PARENT_RELATION_LABELS,
    ParentInvitation,
    ParentStudentLink,
    SectionProgress,
    StudentBook,
    Subject,
    TeacherNoteToParent,
    User,
    UserRole,
)
from app.services.analytics import (
    daily_completed_series,
    daily_planned_series,
    student_snapshot,
    subject_breakdown,
)
from app.services.event_triggers import on_teacher_note_created
from app.templating import templates


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teacher/students")


@router.get("/{student_id}")
def student_detail(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
    flash: str | None = None,
):
    student = (
        db.query(User)
        .options(joinedload(User.academic_year))
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
    snapshot = student_snapshot(db, student, today=today)
    subject_stats = subject_breakdown(db, student.id)

    # 30 günlük trend serileri
    completed_series = daily_completed_series(db, student.id, today, 30)
    planned_series = daily_planned_series(db, student.id, today, 30)
    trend_days = sorted(completed_series.keys())
    trend_labels = [d.strftime("%d %b") for d in trend_days]
    trend_completed = [completed_series[d] for d in trend_days]
    trend_planned = [planned_series[d] for d in trend_days]

    # Kitap envanteri (ders bazında kartlarla gösterim için)
    student_books = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    by_subject: dict[Subject, list[StudentBook]] = {}
    for sb in student_books:
        by_subject.setdefault(sb.book.subject, []).append(sb)

    def progress_map(sb: StudentBook) -> dict[int, SectionProgress]:
        return {p.book_section_id: p for p in sb.section_progress}

    # Modal için: kütüphandeki tüm kitaplar derse göre gruplu
    # (zaten atanmış olanlar UI'da disabled gösterilir)
    assigned_book_ids = {sb.book_id for sb in student_books}
    library_books = (
        db.query(Book)
        .options(joinedload(Book.subject), joinedload(Book.sections))
        .filter(Book.teacher_id == user.id)
        .order_by(Book.name)
        .all()
    )
    library_by_subject: dict[Subject, list[Book]] = {}
    for b in library_books:
        library_by_subject.setdefault(b.subject, []).append(b)
    available_count = sum(
        1 for b in library_books if b.id not in assigned_book_ids
    )

    # Öğretmenin kitap setleri (modal'da set'ten uygula sekmesi için)
    book_sets = (
        db.query(BookSet)
        .options(
            joinedload(BookSet.items)
            .joinedload(BookSetItem.book)
            .joinedload(Book.subject)
        )
        .filter(BookSet.teacher_id == user.id)
        .order_by(BookSet.name)
        .all()
    )

    # Veliler sekmesi: bağlı veliler + bekleyen davetler
    parent_links = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.parent))
        .filter(ParentStudentLink.student_id == student.id)
        .all()
    )
    from datetime import datetime, timezone as _tz
    now = datetime.now(_tz.utc)
    parent_invitations = (
        db.query(ParentInvitation)
        .filter(
            ParentInvitation.student_id == student.id,
            ParentInvitation.consumed_at.is_(None),
            ParentInvitation.expires_at > now,
        )
        .order_by(ParentInvitation.created_at.desc())
        .all()
    )

    # Faz 7+: Track mismatch + diagnostic
    from app.services.suggestions import (
        book_track_mismatches,
        diagnostic_priority_subjects,
    )
    track_mismatches = book_track_mismatches(db, student)
    diagnostic_subjects = (
        diagnostic_priority_subjects(db, student)
        if student.is_graduate else []
    )

    # Koçluk takvimi (hafta anchor'ı) — overview sekmesinde gösterilir
    from app.routes.teacher_program import _resolve_week_anchor
    week_anchor = _resolve_week_anchor(db, student)
    anchor_is_manual = student.program_anchor_date is not None
    TR_WEEKDAYS_LOCAL = ["Pazartesi", "Salı", "Çarşamba", "Perşembe",
                         "Cuma", "Cumartesi", "Pazar"]

    return templates.TemplateResponse(
        "teacher/student_detail.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "snapshot": snapshot,
            "projection": snapshot.projection,
            "warnings": snapshot.warnings,
            "subject_stats": subject_stats,
            "trend_labels": trend_labels,
            "trend_completed": trend_completed,
            "trend_planned": trend_planned,
            "by_subject": by_subject,
            "progress_map": progress_map,
            "library_by_subject": library_by_subject,
            "available_count": available_count,
            "book_sets": book_sets,
            "assigned_book_ids": assigned_book_ids,
            "parent_links": parent_links,
            "parent_invitations": parent_invitations,
            "PARENT_RELATION_LABELS": PARENT_RELATION_LABELS,
            "flash": flash,
            "track_mismatches": track_mismatches,
            "diagnostic_subjects": diagnostic_subjects,
            "week_anchor": week_anchor,
            "anchor_is_manual": anchor_is_manual,
            "tr_weekdays": TR_WEEKDAYS_LOCAL,
        },
    )


@router.post("/{student_id}/books/assign")
async def assign_books_to_student(
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

    form = await request.form()
    raw_ids = form.getlist("book_ids")
    selected_ids: set[int] = set()
    for v in raw_ids:
        try:
            selected_ids.add(int(v))
        except (TypeError, ValueError):
            continue

    if not selected_ids:
        return RedirectResponse(
            url=f"/teacher/students/{student_id}#books",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Sadece bu öğretmenin sahip olduğu kitaplar
    valid_books = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(
            Book.teacher_id == user.id,
            Book.id.in_(selected_ids),
        )
        .all()
    )

    # Zaten atanmış olanlar atlanır
    already_assigned = {
        sb.book_id
        for sb in db.query(StudentBook)
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.book_id.in_({b.id for b in valid_books}),
        )
        .all()
    }

    # Baseline (önceden çözülmüş test) kabul et:
    # form alan adı: baseline_<book_id>_<section_id> = N (opsiyonel, default 0)
    def _baseline(book_id: int, section_id: int, max_allowed: int) -> int:
        raw = (form.get(f"baseline_{book_id}_{section_id}") or "").strip()
        if not raw:
            return 0
        try:
            v = int(raw)
        except ValueError:
            return 0
        if v < 0:
            return 0
        if v > max_allowed:
            return max_allowed
        return v

    for book in valid_books:
        if book.id in already_assigned:
            continue
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb)
        db.flush()
        for section in book.sections:
            done = _baseline(book.id, section.id, section.test_count)
            db.add(
                SectionProgress(
                    student_book_id=sb.id,
                    book_section_id=section.id,
                    reserved_count=0,
                    completed_count=done,
                )
            )

    db.commit()
    return RedirectResponse(
        url=f"/teacher/students/{student_id}#books",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ---------------------------- Veliye not gönder ----------------------------


@router.post("/{student_id}/parent-note")
def send_parent_note(
    student_id: int,
    request: Request,
    body: str = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen, öğrenciye bağlı tüm velilere özel not gönderir.

    Akış: TeacherNoteToParent kaydı oluştur → on_teacher_note_created her veli
    için teacher_note bildirimi enqueue eder → dispatcher gönderir.

    GİZLİLİK: not öğrencinin gözüne kesinlikle gösterilmez (öğrenci tarafındaki
    sorgular bu tabloyu kullanmaz; testle pinlenmesi gereken kontrol).
    """
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

    text = (body or "").strip()
    if len(text) < 10:
        msg = "Not en az 10 karakter olmalıdır."
        return RedirectResponse(
            url=f"/teacher/students/{student_id}?flash={quote(msg)}#parents",
            status_code=303,
        )
    if len(text) > 2000:
        text = text[:2000]

    # Bağlı veli yoksa erken bildir (yine de not kaydedilebilir ama anlamsız)
    has_parent = (
        db.query(ParentStudentLink)
        .filter(ParentStudentLink.student_id == student.id)
        .first()
    )
    if not has_parent:
        msg = "Bu öğrenciye henüz bağlı veli yok; davet göndererek başlayın."
        return RedirectResponse(
            url=f"/teacher/students/{student_id}?flash={quote(msg)}#parents",
            status_code=303,
        )

    note = TeacherNoteToParent(
        student_id=student.id,
        teacher_id=user.id,
        body=text,
    )
    db.add(note)
    db.flush()

    summary = on_teacher_note_created(db, note)
    db.commit()

    fired = summary.get("fired", 0)
    if fired == 0:
        msg = "Not kaydedildi ancak aktif veli bulunamadı."
    else:
        msg = f"Not {fired} veliye iletildi (kuyruğa alındı)."
    return RedirectResponse(
        url=f"/teacher/students/{student_id}?flash={quote(msg)}#parents",
        status_code=303,
    )
