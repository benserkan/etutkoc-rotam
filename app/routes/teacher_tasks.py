from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import (
    Book,
    BookSection,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.task_service import ReservationError, release_task_items, reserve_item
from app.templating import templates


router = APIRouter(prefix="/teacher")


def _ensure_student(db: Session, teacher_id: int, student_id: int) -> User:
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == teacher_id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    return student


def _parse_int_or_none(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _week_url(student_id: int, task_date: date) -> str:
    return f"/teacher/students/{student_id}/week?date={task_date.isoformat()}"


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _render_day_card(
    request: Request, user: User, db: Session, student: User, day: date,
    keep_open: str | None = "stay-open",
):
    """Swap sonrası day-card render eden helper.

    keep_open default 'stay-open' — kullanıcı az önce etkileşimde bulundu, kart açık kalsın.
    'add-form' iletilirse hem kart hem de inline + Görev ekle formu açık kalır.
    """
    from app.routes.teacher_program import build_day_card_context
    ctx = build_day_card_context(db, student, day)
    response = templates.TemplateResponse(
        "teacher/partials/day_card.html",
        {"request": request, "user": user, "keep_open": keep_open, **ctx},
    )
    # Sidebar reserved/remaining sayıları görev ekle/sil sonrası güncellensin
    response.headers["HX-Trigger"] = "tasks-changed"
    return response


@router.post("/students/{student_id}/tasks")
def create_task(
    student_id: int,
    request: Request,
    task_date: str = Form(..., alias="task_date"),
    type: str = Form("test"),
    title: str = Form(""),
    book_id: str = Form(""),
    section_id: str = Form(""),
    planned_count: str = Form(""),
    keep_open: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = _ensure_student(db, user.id, student_id)
    try:
        parsed_date = date.fromisoformat(task_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")

    try:
        task_type = TaskType(type)
    except ValueError:
        task_type = TaskType.TEST

    bk_id = _parse_int_or_none(book_id)
    sec_id = _parse_int_or_none(section_id)
    count = _parse_int_or_none(planned_count)

    # Eğer Test tipi ise kitap/ünite/adet zorunlu
    if task_type == TaskType.TEST and (not bk_id or not sec_id or not count):
        raise HTTPException(status_code=400, detail="Test görevi için kitap, ünite ve adet zorunlu.")

    display_title = title.strip()
    if not display_title:
        if task_type == TaskType.TEST and bk_id and sec_id and count:
            book = db.query(Book).filter(Book.id == bk_id).first()
            section = db.query(BookSection).filter(BookSection.id == sec_id).first()
            unit_word = "deneme" if book and book.type.value in ("brans_denemesi", "genel_deneme") else "test"
            display_title = f"{book.name if book else '-'} — {section.label if section else '-'}: {count} {unit_word}"
        else:
            display_title = task_type.value.capitalize()

    # Max order for this date
    max_order = (
        db.query(Task.order)
        .filter(Task.student_id == student.id, Task.date == parsed_date)
        .order_by(Task.order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 0

    task = Task(
        student_id=student.id,
        date=parsed_date,
        type=task_type,
        title=display_title,
        status=TaskStatus.PENDING,
        order=next_order,
    )
    db.add(task)
    db.flush()

    if bk_id and sec_id and count:
        try:
            reserve_item(db, student_id=student.id, book_id=bk_id, section_id=sec_id, count=count)
        except ReservationError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        item = TaskBookItem(
            task_id=task.id,
            book_id=bk_id,
            book_section_id=sec_id,
            planned_count=count,
            completed_count=0,
        )
        db.add(item)

    db.commit()
    if _is_htmx(request):
        return _render_day_card(
            request, user, db, student, parsed_date,
            keep_open=keep_open or "add-form",
        )
    return RedirectResponse(url=_week_url(student.id, parsed_date), status_code=303)


@router.post("/tasks/{task_id}/delete")
def delete_task(
    task_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .options(joinedload(Task.book_items), joinedload(Task.student))
        .filter(Task.id == task_id)
        .first()
    )
    if not task or task.student.teacher_id != user.id:
        raise HTTPException(status_code=404)
    student = task.student
    task_date = task.date
    release_task_items(db, task.student_id, list(task.book_items))
    db.delete(task)
    db.commit()
    if _is_htmx(request):
        return _render_day_card(request, user, db, student, task_date)
    return RedirectResponse(url=_week_url(student.id, task_date), status_code=303)


@router.get("/tasks/{task_id}/edit")
def edit_task_form(
    task_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
    err: str = "",
):
    task = (
        db.query(Task)
        .options(
            joinedload(Task.student),
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section),
        )
        .filter(Task.id == task_id)
        .first()
    )
    if not task or task.student.teacher_id != user.id:
        raise HTTPException(status_code=404)
    # Öğrencinin kitap envanteri
    from app.models import StudentBook
    assignments = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == task.student_id)
        .all()
    )
    subjects_map = {}
    for sb in assignments:
        subjects_map[sb.book.subject.id] = sb.book.subject
    subjects = sorted(subjects_map.values(), key=lambda s: (s.order, s.name))

    # Tek kalemli görevde mevcut seçimleri çıkar (form pre-populate için)
    current_subject_id = None
    current_book_id = None
    current_section_id = None
    current_section_remaining = None
    if len(task.book_items) == 1:
        it = task.book_items[0]
        current_book_id = it.book_id
        current_section_id = it.book_section_id
        if it.book and it.book.subject:
            current_subject_id = it.book.subject_id
        # Hedef section'da kalan kapasite
        sp = next(
            (p for sb in assignments if sb.book_id == it.book_id
             for p in sb.section_progress if p.book_section_id == it.book_section_id),
            None,
        )
        if sp and it.section:
            current_section_remaining = it.section.test_count - sp.reserved_count - sp.completed_count

    return templates.TemplateResponse(
        "teacher/task_edit.html",
        {
            "request": request,
            "user": user,
            "task": task,
            "student": task.student,
            "assignments": assignments,
            "subjects": subjects,
            "task_types": list(TaskType),
            "current_subject_id": current_subject_id,
            "current_book_id": current_book_id,
            "current_section_id": current_section_id,
            "current_section_remaining": current_section_remaining,
            "flash_err": err,
        },
    )


@router.post("/tasks/{task_id}/edit")
def edit_task(
    task_id: int,
    type: str = Form("test"),
    title: str = Form(""),
    task_date: str = Form(...),
    book_id: str = Form(""),
    section_id: str = Form(""),
    planned_count: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Görev düzenleme.

    - Tek kalemli görevde + book_id/section_id/planned_count gönderilmişse: kaynağı ve sayıyı
      birlikte günceller; rezervleri otomatik dengeler; başlığı otomatik üretir.
    - Aksi halde sadece tarih/tip/başlığı günceller (çok-kalemli görev senaryosu).
    """
    from urllib.parse import quote
    task = (
        db.query(Task)
        .options(
            joinedload(Task.student),
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section),
        )
        .filter(Task.id == task_id)
        .first()
    )
    if not task or task.student.teacher_id != user.id:
        raise HTTPException(status_code=404)
    try:
        new_date = date.fromisoformat(task_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")
    try:
        new_type = TaskType(type)
    except ValueError:
        new_type = task.type

    def _err_redirect(msg: str):
        return RedirectResponse(
            url=f"/teacher/tasks/{task_id}/edit?err={quote(msg)}",
            status_code=303,
        )

    # Tek kalemli + tüm kaynak alanları gönderildiyse: birleşik güncelleme
    is_single_full = (
        len(task.book_items) == 1
        and book_id.strip() and section_id.strip() and planned_count.strip()
    )
    if is_single_full:
        try:
            new_book_id = int(book_id)
            new_section_id = int(section_id)
            new_count = int(planned_count)
        except ValueError:
            return _err_redirect("Geçersiz kaynak seçimi.")
        if new_count < 1:
            return _err_redirect("Test sayısı en az 1 olmalı.")

        item = task.book_items[0]
        source_changed = (new_book_id != item.book_id) or (new_section_id != item.book_section_id)

        # Tamamlanmış varsa kaynak değişimini engelle
        if source_changed and item.completed_count > 0:
            return _err_redirect(
                f"Bu görevde {item.completed_count} test tamamlanmış. Kaynak değişimi yapılamaz; "
                f"yeni görev oluşturup eskisini silmek daha doğru."
            )
        if new_count < item.completed_count:
            return _err_redirect(
                f"Yeni sayı tamamlanmış miktarın altına düşemez (en az {item.completed_count})."
            )

        # Yeni kitap+section'ın bu öğrenciye ait olduğunu doğrula
        new_book = db.query(Book).filter(Book.id == new_book_id).first()
        new_section = db.query(BookSection).filter(BookSection.id == new_section_id).first()
        if not new_book or not new_section or new_section.book_id != new_book_id:
            return _err_redirect("Kitap/bölüm uyumsuz.")

        # Eski kaynaktan henüz tamamlanmamış kısmı iade et
        old_pending = item.planned_count - item.completed_count
        if old_pending > 0:
            from app.services.task_service import release_item
            release_item(
                db,
                student_id=task.student_id,
                book_id=item.book_id,
                section_id=item.book_section_id,
                count=old_pending,
            )

        # Yeni kaynakta gereken yeni rezerv miktarı
        new_pending = new_count - (item.completed_count if not source_changed else 0)
        if new_pending > 0:
            try:
                from app.services.task_service import reserve_item
                reserve_item(
                    db,
                    student_id=task.student_id,
                    book_id=new_book_id,
                    section_id=new_section_id,
                    count=new_pending,
                )
            except ReservationError as e:
                db.rollback()
                return _err_redirect(str(e))

        # Item'ı güncelle
        item.book_id = new_book_id
        item.book_section_id = new_section_id
        item.planned_count = new_count
        if source_changed:
            item.completed_count = 0  # kaynak değişti, eski tamamlama anlamsız

        # Başlığı otomatik üret
        unit_word = "deneme" if new_book.type.value in ("brans_denemesi", "genel_deneme") else "test"
        task.title = f"{new_book.name} — {new_section.label}: {new_count} {unit_word}"
    else:
        # Çok-kalemli görev veya kaynak alanları boş → sadece üst-bilgi güncellemesi
        if title.strip():
            task.title = title.strip()

    task.type = new_type
    task.date = new_date
    db.commit()
    return RedirectResponse(url=_week_url(task.student_id, new_date), status_code=303)


@router.post("/tasks/{task_id}/items")
def add_item(
    task_id: int,
    book_id: int = Form(...),
    section_id: int = Form(...),
    planned_count: int = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .options(joinedload(Task.student))
        .filter(Task.id == task_id)
        .first()
    )
    if not task or task.student.teacher_id != user.id:
        raise HTTPException(status_code=404)
    try:
        reserve_item(
            db,
            student_id=task.student_id,
            book_id=book_id,
            section_id=section_id,
            count=planned_count,
        )
    except ReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    db.add(TaskBookItem(
        task_id=task.id,
        book_id=book_id,
        book_section_id=section_id,
        planned_count=planned_count,
        completed_count=0,
    ))
    db.commit()
    return RedirectResponse(url=f"/teacher/tasks/{task_id}/edit", status_code=303)


@router.post("/tasks/{task_id}/items/{item_id}/delete")
def delete_item(
    task_id: int,
    item_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    item = (
        db.query(TaskBookItem)
        .options(joinedload(TaskBookItem.task).joinedload(Task.student))
        .filter(TaskBookItem.id == item_id, TaskBookItem.task_id == task_id)
        .first()
    )
    if not item or item.task.student.teacher_id != user.id:
        raise HTTPException(status_code=404)
    release_task_items(db, item.task.student_id, [item])
    db.delete(item)
    db.commit()
    return RedirectResponse(url=f"/teacher/tasks/{task_id}/edit", status_code=303)
