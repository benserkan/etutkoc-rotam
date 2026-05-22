"""API v2 — Haftalık plan (Paket 3.5a.1).

Jinja `/teacher/students/{id}/week` ekranının inline akışını JSON kontratıyla
karşılayan endpoint'ler. Mevcut `teacher.py` içindeki `GET .../week` endpoint'i
geriye uyumlu kalır; bu modül **yeni** endpoint'leri toplar.

Endpoint haritası:
  GET    /teacher/students/{id}/week-notes?week_start=YYYY-MM-DD
  POST   /teacher/students/{id}/week-notes                       (add)
  DELETE /teacher/students/{id}/week-notes/{note_id}
  POST   /teacher/students/{id}/week-notes/{note_id}/toggle
  POST   /teacher/students/{id}/publish-day                      (form-equiv JSON)
  POST   /teacher/students/{id}/publish-week
  POST   /teacher/students/{id}/tasks/reorder
  POST   /teacher/students/{id}/program/notify-parents
  GET    /teacher/students/{id}/sidebar-items?subject_id=
  GET    /teacher/students/{id}/books-by-subject?subject_id=
  GET    /teacher/students/{id}/book-sections?book_id=
  GET    /teacher/students/{id}/section-stats?section_id=
  GET    /teacher/students/{id}/review-struggle-suggestions?subject_id=&target_date=

Servisler dokunulmaz; sadece JSON adapter rolündedir.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    Book,
    BookSection,
    StudentBook,
    Task,
    User,
    UserRole,
    WeekNote,
)
from app.routes.api_v2.dependencies import _auth_error, assert_active_coaching, get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.teacher import (
    BookOption,
    BookOptionsResponse,
    NotifyParentsBody,
    NotifyParentsResult,
    PublishDayBody,
    PublishResult,
    PublishWeekBody,
    ReviewStruggleChip,
    ReviewStruggleResponse,
    SectionOption,
    SectionOptionsResponse,
    SectionStatsResponse,
    SidebarBook,
    SidebarResponse,
    SidebarSection,
    SidebarSubject,
    SidebarSubjectSummary,
    TasksReorderBody,
    TasksReorderResult,
    TeacherWeekNote,
    WeekNoteAddBody,
    WeekNoteToggleResult,
)
from app.routes.api_v2.schemas.library import DeletedRef


router = APIRouter(prefix="/teacher", tags=["v2-teacher-weekly-plan"])


# =============================================================================
# Auth + helpers
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


def _get_owned_student(db: Session, student_id: int, teacher_id: int) -> User:
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


def _parse_iso(value: str, code: str = "invalid_date") -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _validation_error(code, "Tarih formatı YYYY-MM-DD olmalı.")


def _invalidate_week(teacher_id: int, student_id: int) -> list[str]:
    return [
        f"teacher:{teacher_id}:students:{student_id}:week",
        f"teacher:{teacher_id}:students:{student_id}:sidebar",
        f"teacher:{teacher_id}:students:{student_id}:notes",
        f"teacher:{teacher_id}:students:{student_id}",
    ]


# =============================================================================
# Hafta notları
# =============================================================================


def _load_week_notes(db: Session, student_id: int, week_start: date) -> list[WeekNote]:
    return (
        db.query(WeekNote)
        .filter(
            WeekNote.student_id == student_id,
            WeekNote.week_start == week_start,
        )
        .order_by(WeekNote.order.asc(), WeekNote.id.asc())
        .all()
    )


def _notes_dto(notes: list[WeekNote]) -> list[TeacherWeekNote]:
    return [
        TeacherWeekNote(id=n.id, body=n.body, order=n.order, is_done=bool(n.is_done))
        for n in notes
    ]


@router.get(
    "/students/{student_id}/week-notes",
    response_model=list[TeacherWeekNote],
)
def list_week_notes(
    student_id: int,
    week_start: str = Query(...),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> list[TeacherWeekNote]:
    student = _get_owned_student(db, student_id, user.id)
    ws = _parse_iso(week_start)
    return _notes_dto(_load_week_notes(db, student.id, ws))


@router.post(
    "/students/{student_id}/week-notes",
    response_model=MutationResponse[TeacherWeekNote],
)
def add_week_note(
    student_id: int,
    body: WeekNoteAddBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[TeacherWeekNote]:
    student = _get_owned_student(db, student_id, user.id)
    text = (body.body or "").strip()
    if not text:
        raise _validation_error("body_required", "Not metni boş olamaz.")
    ws = _parse_iso(body.week_start, "invalid_week_start")
    existing = _load_week_notes(db, student.id, ws)
    next_order = (existing[-1].order + 1) if existing else 0
    note = WeekNote(
        student_id=student.id,
        week_start=ws,
        body=text,
        order=next_order,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return MutationResponse[TeacherWeekNote](
        data=TeacherWeekNote(id=note.id, body=note.body, order=note.order, is_done=bool(note.is_done)),
        invalidate=_invalidate_week(user.id, student.id),
    )


@router.delete(
    "/students/{student_id}/week-notes/{note_id}",
    response_model=MutationResponse[DeletedRef],
)
def delete_week_note(
    student_id: int,
    note_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[DeletedRef]:
    student = _get_owned_student(db, student_id, user.id)
    note = (
        db.query(WeekNote)
        .filter(WeekNote.id == note_id, WeekNote.student_id == student.id)
        .first()
    )
    if not note:
        raise _not_found("note_not_found", "Not bulunamadı.")
    deleted_id = note.id
    db.delete(note)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=deleted_id),
        invalidate=_invalidate_week(user.id, student.id),
    )


@router.post(
    "/students/{student_id}/week-notes/{note_id}/toggle",
    response_model=MutationResponse[WeekNoteToggleResult],
)
def toggle_week_note(
    student_id: int,
    note_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[WeekNoteToggleResult]:
    student = _get_owned_student(db, student_id, user.id)
    note = (
        db.query(WeekNote)
        .filter(WeekNote.id == note_id, WeekNote.student_id == student.id)
        .first()
    )
    if not note:
        raise _not_found("note_not_found", "Not bulunamadı.")
    note.is_done = not note.is_done
    db.commit()
    return MutationResponse[WeekNoteToggleResult](
        data=WeekNoteToggleResult(id=note.id, is_done=bool(note.is_done)),
        invalidate=_invalidate_week(user.id, student.id),
    )


# =============================================================================
# Publish day / week
# =============================================================================


def _week_draft_total(db: Session, student_id: int, start: date) -> int:
    end = start + timedelta(days=6)
    return (
        db.query(Task)
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end,
            Task.is_draft.is_(True),
        )
        .count()
    )


@router.post(
    "/students/{student_id}/publish-day",
    response_model=MutationResponse[PublishResult],
)
def publish_day(
    student_id: int,
    body: PublishDayBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[PublishResult]:
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    target = _parse_iso(body.task_date)
    now = datetime.now(timezone.utc)
    drafts = (
        db.query(Task)
        .filter(
            Task.student_id == student.id,
            Task.date == target,
            Task.is_draft.is_(True),
        )
        .all()
    )
    for t in drafts:
        t.is_draft = False
        t.published_at = now
    db.commit()
    week_start = target - timedelta(days=target.weekday())
    return MutationResponse[PublishResult](
        data=PublishResult(
            published_count=len(drafts),
            week_draft_total=_week_draft_total(db, student.id, week_start),
        ),
        invalidate=_invalidate_week(user.id, student.id),
    )


@router.post(
    "/students/{student_id}/publish-week",
    response_model=MutationResponse[PublishResult],
)
def publish_week(
    student_id: int,
    body: PublishWeekBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[PublishResult]:
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    start = _parse_iso(body.week_start, "invalid_week_start")
    end = start + timedelta(days=6)
    now = datetime.now(timezone.utc)
    drafts = (
        db.query(Task)
        .filter(
            Task.student_id == student.id,
            Task.date >= start,
            Task.date <= end,
            Task.is_draft.is_(True),
        )
        .all()
    )
    published_count = len(drafts)
    for t in drafts:
        t.is_draft = False
        t.published_at = now
    db.commit()
    return MutationResponse[PublishResult](
        data=PublishResult(
            published_count=published_count,
            week_draft_total=_week_draft_total(db, student.id, start),
        ),
        invalidate=_invalidate_week(user.id, student.id),
    )


# =============================================================================
# Tasks reorder
# =============================================================================


@router.post(
    "/students/{student_id}/tasks/reorder",
    response_model=MutationResponse[TasksReorderResult],
)
def reorder_tasks(
    student_id: int,
    body: TasksReorderBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[TasksReorderResult]:
    student = _get_owned_student(db, student_id, user.id)
    target = _parse_iso(body.task_date)
    if not body.task_ids:
        raise _validation_error("empty_task_ids", "Sıralanacak görev yok.")
    tasks = (
        db.query(Task)
        .filter(
            Task.id.in_(body.task_ids),
            Task.student_id == student.id,
            Task.date == target,
        )
        .all()
    )
    by_id = {t.id: t for t in tasks}
    reordered = 0
    for new_order, tid in enumerate(body.task_ids):
        t = by_id.get(tid)
        if t is None:
            continue
        if t.order != new_order:
            reordered += 1
        t.order = new_order
    db.commit()
    return MutationResponse[TasksReorderResult](
        data=TasksReorderResult(reordered_count=reordered),
        invalidate=_invalidate_week(user.id, student.id),
    )


# =============================================================================
# Notify parents
# =============================================================================


@router.post(
    "/students/{student_id}/program/notify-parents",
    response_model=MutationResponse[NotifyParentsResult],
)
def notify_parents(
    student_id: int,
    body: NotifyParentsBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[NotifyParentsResult]:
    from app.services.event_triggers import on_program_published

    student = _get_owned_student(db, student_id, user.id)
    ws = _parse_iso(body.week_start, "invalid_week_start")
    summary = on_program_published(db, student=student, week_start=ws)
    db.commit()

    no_tasks = bool(summary.get("no_tasks"))
    fired = int(summary.get("fired", 0) or 0)
    skipped = int(summary.get("skipped_recent", 0) or 0)

    if no_tasks:
        message = "Bu hafta için görev bulunmuyor; veliye duyuru gönderilmedi."
    elif fired == 0 and skipped > 0:
        message = (
            "Velilere son 24 saat içinde aynı program duyuruldu — yeniden gönderilmedi."
        )
    elif fired == 0:
        message = "Bağlı veli bulunamadı; duyuru yapılmadı."
    else:
        suffix = f" ({skipped} veli son 24 saat içinde duyurulmuş, atlandı)" if skipped else ""
        message = f"Program {fired} veliye duyuruldu.{suffix}"

    return MutationResponse[NotifyParentsResult](
        data=NotifyParentsResult(
            fired=fired, skipped_recent=skipped, no_tasks=no_tasks, message=message,
        ),
        invalidate=_invalidate_week(user.id, student.id),
    )


# =============================================================================
# Sidebar — 3 seviyeli (subject → book → section)
# =============================================================================


def _build_sidebar(
    db: Session, student_id: int, focused_subject_id: int | None,
) -> SidebarResponse:
    sbs = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student_id)
        .all()
    )
    if focused_subject_id is not None:
        sbs = [sb for sb in sbs if sb.book.subject_id == focused_subject_id]

    by_subject: dict[int, list[StudentBook]] = {}
    subject_objs: dict[int, object] = {}
    for sb in sbs:
        s = sb.book.subject
        subject_objs[s.id] = s
        by_subject.setdefault(s.id, []).append(sb)

    subjects: list[SidebarSubject] = []
    grand_total = grand_completed = grand_reserved = grand_remaining = 0

    for sid in sorted(subject_objs, key=lambda i: (subject_objs[i].order, subject_objs[i].name)):
        subj = subject_objs[sid]
        sub_books: list[SidebarBook] = []
        sub_total = sub_completed = sub_reserved = sub_remaining = 0

        for sb in by_subject[sid]:
            pmap = {p.book_section_id: p for p in sb.section_progress}
            sections_out: list[SidebarSection] = []
            b_total = b_completed = b_reserved = b_remaining = 0
            for sec in sorted(sb.book.sections or [], key=lambda s: (s.order, s.id)):
                sp = pmap.get(sec.id)
                comp = int(sp.completed_count) if sp else 0
                res = int(sp.reserved_count) if sp else 0
                tot = int(sec.test_count)
                rem = max(0, tot - comp - res)
                sections_out.append(SidebarSection(
                    id=sec.id,
                    label=sec.label,
                    topic_name=sec.topic.name if sec.topic else None,
                    total=tot, completed=comp, reserved=res, remaining=rem,
                ))
                b_total += tot
                b_completed += comp
                b_reserved += res
                b_remaining += rem
            sub_books.append(SidebarBook(
                id=sb.book.id,
                name=sb.book.name,
                type=sb.book.type.value if sb.book.type else "soru_bankasi",
                total=b_total, completed=b_completed, reserved=b_reserved,
                remaining=b_remaining,
                sections=sections_out,
            ))
            sub_total += b_total
            sub_completed += b_completed
            sub_reserved += b_reserved
            sub_remaining += b_remaining

        subjects.append(SidebarSubject(
            id=subj.id,
            name=subj.name,
            summary=SidebarSubjectSummary(
                total=sub_total, completed=sub_completed,
                reserved=sub_reserved, remaining=sub_remaining,
                books_count=len(sub_books),
            ),
            books=sub_books,
        ))
        grand_total += sub_total
        grand_completed += sub_completed
        grand_reserved += sub_reserved
        grand_remaining += sub_remaining

    return SidebarResponse(
        subjects=subjects,
        focused_subject_id=focused_subject_id,
        grand_total=grand_total,
        grand_completed=grand_completed,
        grand_reserved=grand_reserved,
        grand_remaining=grand_remaining,
    )


@router.get(
    "/students/{student_id}/sidebar-items",
    response_model=SidebarResponse,
)
def sidebar_items(
    student_id: int,
    subject_id: str = Query(""),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> SidebarResponse:
    student = _get_owned_student(db, student_id, user.id)
    focused: int | None = None
    s = (subject_id or "").strip()
    if s:
        try:
            focused = int(s)
        except ValueError:
            focused = None
    return _build_sidebar(db, student.id, focused)


# =============================================================================
# Cascade — books-by-subject / book-sections / section-stats
# =============================================================================


@router.get(
    "/students/{student_id}/books-by-subject",
    response_model=BookOptionsResponse,
)
def books_by_subject(
    student_id: int,
    subject_id: str = Query(""),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> BookOptionsResponse:
    student = _get_owned_student(db, student_id, user.id)
    parsed: int | None = None
    s = (subject_id or "").strip()
    if s:
        try:
            parsed = int(s)
        except ValueError:
            parsed = None

    sbs = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    out: list[BookOption] = []
    for sb in sbs:
        if parsed is None or sb.book.subject_id == parsed:
            out.append(BookOption(id=sb.book.id, name=sb.book.name))
    out.sort(key=lambda b: b.name)
    return BookOptionsResponse(items=out, subject_id=parsed)


@router.get(
    "/students/{student_id}/book-sections",
    response_model=SectionOptionsResponse,
)
def book_sections(
    student_id: int,
    book_id: int = Query(...),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> SectionOptionsResponse:
    student = _get_owned_student(db, student_id, user.id)
    sb = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student.id, StudentBook.book_id == book_id)
        .first()
    )
    if not sb:
        # Cross-tenant veya atanmamış — boş liste döndür (formda sade "kitap seçilmedi")
        return SectionOptionsResponse(items=[], is_deneme=False)
    pmap = {p.book_section_id: p for p in sb.section_progress}
    items: list[SectionOption] = []
    for sec in sorted(sb.book.sections or [], key=lambda s: (s.order, s.id)):
        sp = pmap.get(sec.id)
        res = int(sp.reserved_count) if sp else 0
        done = int(sp.completed_count) if sp else 0
        rem = max(0, int(sec.test_count) - res - done)
        items.append(SectionOption(
            id=sec.id,
            label=sec.label,
            topic_name=sec.topic.name if sec.topic else None,
            remaining=rem,
            total=int(sec.test_count),
        ))
    is_deneme = bool(
        sb.book.type and sb.book.type.value in ("brans_denemesi", "genel_deneme")
    )
    return SectionOptionsResponse(items=items, is_deneme=is_deneme)


@router.get(
    "/students/{student_id}/section-stats",
    response_model=SectionStatsResponse,
)
def section_stats(
    student_id: int,
    section_id: int = Query(...),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> SectionStatsResponse:
    student = _get_owned_student(db, student_id, user.id)
    sec = (
        db.query(BookSection)
        .options(joinedload(BookSection.topic), joinedload(BookSection.book))
        .filter(BookSection.id == section_id)
        .first()
    )
    if not sec:
        raise _not_found("section_not_found", "Bölüm bulunamadı.")
    sb = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.section_progress))
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.book_id == sec.book_id,
        )
        .first()
    )
    completed = reserved = 0
    if sb:
        for sp in sb.section_progress:
            if sp.book_section_id == sec.id:
                completed = int(sp.completed_count)
                reserved = int(sp.reserved_count)
                break
    total = int(sec.test_count)
    remaining = max(0, total - completed - reserved)
    return SectionStatsResponse(
        section_id=sec.id,
        section_label=sec.label,
        book_name=sec.book.name,
        topic_name=sec.topic.name if sec.topic else None,
        total=total,
        completed=completed,
        reserved=reserved,
        remaining=remaining,
    )


# =============================================================================
# Review struggle suggestions (FSRS chip list)
# =============================================================================


@router.get(
    "/students/{student_id}/review-struggle-suggestions",
    response_model=ReviewStruggleResponse,
)
def review_struggle_suggestions(
    student_id: int,
    subject_id: int = Query(...),
    target_date: str = Query(...),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> ReviewStruggleResponse:
    student = _get_owned_student(db, student_id, user.id)
    target = _parse_iso(target_date, "invalid_target_date")

    items: list[ReviewStruggleChip] = []
    try:
        from app.services.fsrs import struggle_chip_suggestions  # type: ignore[attr-defined]
    except Exception:
        struggle_chip_suggestions = None  # noqa: N816

    if struggle_chip_suggestions is not None:
        try:
            raw = struggle_chip_suggestions(
                db, student_id=student.id, subject_id=subject_id, target_date=target,
            )
        except Exception:
            raw = []
        for r in raw or []:
            items.append(ReviewStruggleChip(
                card_id=int(r.get("card_id", 0)),
                topic_name=str(r.get("topic_name", "")),
                state=str(r.get("state", "review")),
                lapse_count=int(r.get("lapse_count", 0) or 0),
                score=int(r.get("score", 0) or 0),
                reasons=list(r.get("reasons", []) or []),
            ))

    return ReviewStruggleResponse(
        items=items,
        target_date=target.isoformat(),
        subject_id=subject_id,
    )
