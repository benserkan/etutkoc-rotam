from datetime import date, datetime, timedelta, timezone

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
    """Day-card HTMX swap + OOB hafta header senkronizasyonu.

    keep_open default 'stay-open' — kullanıcı az önce etkileşimde bulundu, kart açık kalsın.
    'add-form' iletilirse hem kart hem de inline + Görev ekle formu açık kalır.

    Ek olarak: görünmekte olan 7-günlük pencerenin taslak toplamını yeniden
    hesaplar ve `week_draft_oob.html` partial'ını OOB swap ile response'a
    ekler — böylece "Tüm haftayı yayınla (N)" butonu ve sarı banner backend
    ile senkron kalır (publish-day, create, delete, update sonrası).
    """
    from fastapi.responses import HTMLResponse
    from urllib.parse import urlparse, parse_qs

    from app.routes.teacher_program import build_day_card_context

    ctx = build_day_card_context(db, student, day)

    # 7-günlük pencere başlangıcı — HX-Current-URL'den, yoksa bugünden
    start = date.today()
    cur = request.headers.get("HX-Current-URL") or ""
    if cur:
        try:
            qs = parse_qs(urlparse(cur).query)
            raw = (qs.get("start") or qs.get("date") or [""])[0]
            if raw:
                start = date.fromisoformat(raw)
        except (ValueError, TypeError):
            pass
    end = start + timedelta(days=6)

    week_draft_total = (
        db.query(Task)
        .filter(
            Task.student_id == student.id,
            Task.date >= start,
            Task.date <= end,
            Task.is_draft.is_(True),
        )
        .count()
    )

    day_card_html = templates.get_template("teacher/partials/day_card.html").render(
        request=request, user=user, keep_open=keep_open, **ctx,
    )
    oob_html = templates.get_template("teacher/partials/week_draft_oob.html").render(
        request=request, student=student, start=start, end=end,
        week_draft_total=week_draft_total,
    )

    response = HTMLResponse(content=day_card_html + oob_html)
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
    scheduled_hour: str = Form(""),
    link_url: str = Form(""),
    notes: str = Form(""),
    subject_label: str = Form(""),
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
    hour = _parse_int_or_none(scheduled_hour)
    if hour is not None and not (0 <= hour <= 23):
        hour = None
    link = (link_url or "").strip() or None
    notes_clean = (notes or "").strip() or None
    subj_lbl = (subject_label or "").strip()

    # Tipe göre zorunlu alan kontrolü
    if task_type == TaskType.TEST:
        if not bk_id or not sec_id or not count:
            raise HTTPException(status_code=400, detail="Test görevi için kitap, ünite ve adet zorunlu.")
    elif task_type == TaskType.VIDEO:
        if not link:
            raise HTTPException(status_code=400, detail="Video görevi için bağlantı (URL) zorunlu.")
    elif task_type in (TaskType.OZET, TaskType.TEKRAR):
        if not notes_clean and not title.strip():
            raise HTTPException(status_code=400, detail="Bu görev tipi için konu/açıklama zorunlu.")

    display_title = title.strip()
    if not display_title:
        if task_type == TaskType.TEST and bk_id and sec_id and count:
            book = db.query(Book).filter(Book.id == bk_id).first()
            section = db.query(BookSection).filter(BookSection.id == sec_id).first()
            unit_word = "deneme" if book and book.type.value in ("brans_denemesi", "genel_deneme") else "test"
            display_title = f"{book.name if book else '-'} — {section.label if section else '-'}: {count} {unit_word}"
        elif task_type == TaskType.VIDEO:
            # Video başlığı: notes varsa onu, yoksa URL'in kısa hali
            display_title = notes_clean or "Video İzleme"
        elif task_type == TaskType.OZET:
            base = notes_clean or "Özet"
            display_title = f"Özet: {subj_lbl + ' — ' if subj_lbl else ''}{base}"[:200]
        elif task_type == TaskType.TEKRAR:
            base = notes_clean or "Konu tekrarı"
            display_title = f"Tekrar: {subj_lbl + ' — ' if subj_lbl else ''}{base}"[:200]
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

    # Smart draft default — geçmiş+bugün canlı, yarın+ taslak.
    # Mantık: öğrenci o gün çalışıyorsa kaydı görmesi zaten gerekli;
    # gelecek günler için öğretmen ayarlasın, sonra "yayınla"sın.
    today = date.today()
    is_draft_default = parsed_date > today
    task = Task(
        student_id=student.id,
        date=parsed_date,
        type=task_type,
        title=display_title,
        status=TaskStatus.PENDING,
        order=next_order,
        scheduled_hour=hour,
        notes=notes_clean,
        link_url=link,
        is_draft=is_draft_default,
        published_at=None if is_draft_default else datetime.now(timezone.utc),
    )
    db.add(task)
    db.flush()

    # TaskBookItem yalnızca Test tipinde + tüm alanlar verildiyse
    if task_type == TaskType.TEST and bk_id and sec_id and count:
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


@router.post("/students/{student_id}/publish-day")
def publish_day_tasks(
    student_id: int,
    request: Request,
    task_date: str = Form(..., alias="task_date"),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Bir günün tüm taslak görevlerini yayına al — öğrencinin paneline indirir.

    Sadece is_draft=True olanlar etkilenir; zaten yayında olanlar dokunulmaz.
    published_at o anki UTC zamanı ile damgalanır (audit + sonraki bildirim
    tetiklemelerinde kullanılır).
    """
    student = _ensure_student(db, user.id, student_id)
    try:
        parsed_date = date.fromisoformat(task_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")

    now = datetime.now(timezone.utc)
    drafts = (
        db.query(Task)
        .filter(
            Task.student_id == student.id,
            Task.date == parsed_date,
            Task.is_draft.is_(True),
        )
        .all()
    )
    for t in drafts:
        t.is_draft = False
        t.published_at = now
    db.commit()

    if _is_htmx(request):
        return _render_day_card(request, user, db, student, parsed_date, keep_open=None)
    return RedirectResponse(url=_week_url(student.id, parsed_date), status_code=303)


@router.post("/students/{student_id}/publish-week")
def publish_week_tasks(
    student_id: int,
    request: Request,
    week_start: str = Form(..., alias="week_start"),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """7 günlük pencerenin tüm taslaklarını yayına al.

    Hafta header'ındaki "🚀 Tüm haftayı yayınla" butonundan tetiklenir.
    Sayfa redirect ile yenilenir — kullanıcı yeni durumu görsün.
    """
    student = _ensure_student(db, user.id, student_id)
    try:
        start = date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")
    end = start + timedelta(days=6)

    now = datetime.now(timezone.utc)
    db.query(Task).filter(
        Task.student_id == student.id,
        Task.date >= start,
        Task.date <= end,
        Task.is_draft.is_(True),
    ).update(
        {"is_draft": False, "published_at": now},
        synchronize_session=False,
    )
    db.commit()

    from urllib.parse import quote
    return RedirectResponse(
        url=f"/teacher/students/{student.id}/week?start={start.isoformat()}&ok={quote('Tüm taslak görevler yayınlandı')}",
        status_code=303,
    )


@router.post("/students/{student_id}/tasks/reorder")
def reorder_tasks(
    student_id: int,
    request: Request,
    task_date: str = Form(..., alias="task_date"),
    task_ids: str = Form(..., alias="task_ids"),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Bir günün görevlerini yeni sırada güncelle (sürükle-bırak sonrası).

    task_ids: virgülle ayrılmış sıralı id listesi. Sadece scheduled_hour=NULL
    olan görevlerin manuel sırası anlamlıdır; saat atanmışlar zaten kronolojik
    sıralandığı için burada yeni order yine de yazılır ama görüntü değişmez.
    """
    student = _ensure_student(db, user.id, student_id)
    try:
        parsed_date = date.fromisoformat(task_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")

    ids: list[int] = []
    for raw in task_ids.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            ids.append(int(raw))
        except ValueError:
            continue
    if not ids:
        raise HTTPException(status_code=400, detail="Sıralanacak görev yok")

    # Sadece bu öğrenciye ve bu güne ait id'leri kabul et — güvenlik
    tasks = (
        db.query(Task)
        .filter(
            Task.id.in_(ids),
            Task.student_id == student.id,
            Task.date == parsed_date,
        )
        .all()
    )
    task_by_id = {t.id: t for t in tasks}
    for new_order, tid in enumerate(ids):
        t = task_by_id.get(tid)
        if t is not None:
            t.order = new_order
    db.commit()

    if _is_htmx(request):
        return _render_day_card(request, user, db, student, parsed_date, keep_open=None)
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
    scheduled_hour: str = Form(""),
    link_url: str = Form(""),
    notes: str = Form(""),
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
    # Saat (opsiyonel) — boş string NULL anlamına gelir, sayısal olmayan dair tutmaz
    sh = _parse_int_or_none(scheduled_hour)
    task.scheduled_hour = sh if (sh is not None and 0 <= sh <= 23) else None
    # Tip-spesifik içerik — link_url (video) ve notes (özet/tekrar/diğer)
    new_link = (link_url or "").strip()
    task.link_url = new_link or None
    new_notes = (notes or "").strip()
    task.notes = new_notes or None
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
