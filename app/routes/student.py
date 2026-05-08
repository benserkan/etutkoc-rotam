from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_student
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
    TaskStatus,
    User,
)
from app.services.analytics import (
    daily_completed_series,
    daily_planned_series,
    student_snapshot,
    subject_breakdown,
)
import logging

from app.services.event_triggers import on_task_completed
from app.services.task_service import (
    ReservationError,
    complete_task as svc_complete_task,
    set_item_completion,
    uncomplete_task as svc_uncomplete_task,
)
from app.templating import templates


logger = logging.getLogger(__name__)


def _fire_task_completed_event(db: Session, student: User) -> None:
    """on_task_completed çağrısını try/except ile sarmala — bildirim hatası
    görev tamamlama akışını bozmasın. Çağrıdan sonra commit yapılır.
    """
    try:
        on_task_completed(db, student)
    except Exception as e:
        logger.exception("on_task_completed event hatası (öğrenci=%s): %s", student.id, e)


router = APIRouter(prefix="/student")


TR_WEEKDAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


def _load_day_tasks(db: Session, student_id: int, d: date) -> list[Task]:
    return (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == student_id, Task.date == d)
        .order_by(Task.order, Task.id)
        .all()
    )


def _student_book_progress_map(db: Session, student_id: int) -> dict:
    """Öğrenciye atanmış tüm kitapları döndürür (çift kolona ayrılmış: ders -> [StudentBook])."""
    assignments = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student_id)
        .all()
    )
    subjects_map = {}
    grouped: dict[int, list[StudentBook]] = {}
    for sb in assignments:
        sid = sb.book.subject.id
        subjects_map[sid] = sb.book.subject
        grouped.setdefault(sid, []).append(sb)
    subjects = sorted(subjects_map.values(), key=lambda s: (s.order, s.name))
    summary: dict[int, dict[str, int]] = {}
    for sid, sbs in grouped.items():
        total = sum(sb.total_tests for sb in sbs)
        completed = sum(sb.completed_tests for sb in sbs)
        reserved = sum(sb.reserved_tests for sb in sbs)
        summary[sid] = {
            "total": total,
            "completed": completed,
            "reserved": reserved,
            "remaining": total - completed - reserved,
            "books": len(sbs),
        }
    return {
        "assignments": assignments,
        "subjects": subjects,
        "assignments_by_subject": grouped,
        "subject_summary": summary,
    }


@router.get("")
def student_home(user: User = Depends(require_student)):
    return RedirectResponse(url="/student/day", status_code=303)


@router.get("/day")
def student_day(
    request: Request,
    date_param: str | None = Query(None, alias="date"),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        d = date.fromisoformat(date_param) if date_param else date.today()
    except ValueError:
        d = date.today()

    tasks = _load_day_tasks(db, user.id, d)
    ctx = _student_book_progress_map(db, user.id)

    # Özet
    total_items = sum(len(t.book_items) for t in tasks)
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)

    # Öğrenci kendi analitiği (bugün görüntüleniyorsa anlamlı)
    today = date.today()
    snapshot = student_snapshot(db, user, today=today)
    subject_stats = subject_breakdown(db, user.id)
    completed_series = daily_completed_series(db, user.id, today, 30)
    planned_series = daily_planned_series(db, user.id, today, 30)
    trend_days = sorted(completed_series.keys())
    trend_labels = [dd.strftime("%d %b") for dd in trend_days]
    trend_completed = [completed_series[dd] for dd in trend_days]
    trend_planned = [planned_series[dd] for dd in trend_days]

    # Modal cascade için: ders listesi (öğrenciye atanmış)
    subjects_set = {}
    for sb in ctx["assignments"]:
        subjects_set[sb.book.subject.id] = sb.book.subject
    subject_list = sorted(subjects_set.values(), key=lambda s: (s.order, s.name))

    # Görev başına max yeni sayı hesabı (CHANGE talebi için)
    from app.services.request_service import max_new_count_for_change
    task_max_counts: dict[int, int] = {}
    for t in tasks:
        if len(t.book_items) == 1:
            try:
                task_max_counts[t.id] = max_new_count_for_change(db, t, t.book_items[0])
            except Exception:
                task_max_counts[t.id] = t.book_items[0].planned_count

    return templates.TemplateResponse(
        "student/day.html",
        {
            "request": request,
            "user": user,
            "student": user,
            "day": d,
            "tasks": tasks,
            "total_items": total_items,
            "planned_count": planned,
            "completed_count": completed,
            "prev_date": (d - timedelta(days=1)).isoformat(),
            "next_date": (d + timedelta(days=1)).isoformat(),
            "today": today,
            "tr_weekdays": TR_WEEKDAYS,
            "tr_months": TR_MONTHS,
            "snapshot": snapshot,
            "projection": snapshot.projection,
            "subject_stats": subject_stats,
            "trend_labels": trend_labels,
            "trend_completed": trend_completed,
            "trend_planned": trend_planned,
            "subject_list": subject_list,
            "task_max_counts": task_max_counts,
            **ctx,
        },
    )


@router.get("/week")
def student_week(
    request: Request,
    start_param: str | None = Query(None, alias="start"),
    date_param: str | None = Query(None, alias="date"),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    raw = start_param or date_param
    try:
        start = date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        start = date.today()
    days = [start + timedelta(days=i) for i in range(7)]
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == user.id, Task.date.in_(days))
        .order_by(Task.date, Task.order, Task.id)
        .all()
    )
    tasks_by_day = {d: [] for d in days}
    for t in tasks:
        tasks_by_day[t.date].append(t)
    day_planned = {d: sum(it.planned_count for t in tasks_by_day[d] for it in t.book_items) for d in days}
    day_completed = {d: sum(it.completed_count for t in tasks_by_day[d] for it in t.book_items) for d in days}
    return templates.TemplateResponse(
        "student/week.html",
        {
            "request": request,
            "user": user,
            "student": user,
            "start": start,
            "end": days[-1],
            "days": days,
            "today": date.today(),
            "tasks_by_day": tasks_by_day,
            "day_planned": day_planned,
            "day_completed": day_completed,
            "prev_date": (start - timedelta(days=7)).isoformat(),
            "next_date": (start + timedelta(days=7)).isoformat(),
            "tr_weekdays": TR_WEEKDAYS,
            "tr_months": TR_MONTHS,
        },
    )


@router.get("/weekly-report/print")
def weekly_report_print(
    request: Request,
    start_param: str | None = Query(None, alias="start"),
    date_param: str | None = Query(None, alias="date"),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Veli paylaşımı için yazdırılabilir haftalık performans raporu."""
    raw = start_param or date_param
    try:
        start = date.fromisoformat(raw) if raw else date.today() - timedelta(days=6)
    except ValueError:
        start = date.today() - timedelta(days=6)
    end = start + timedelta(days=6)

    # Haftanın her günü için plan/tamamlama
    days = [start + timedelta(days=i) for i in range(7)]
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == user.id, Task.date.in_(days))
        .order_by(Task.date, Task.order, Task.id)
        .all()
    )
    tasks_by_day = {d: [] for d in days}
    for t in tasks:
        tasks_by_day[t.date].append(t)

    # Gün bazında özet
    day_summary = {}
    for d in days:
        planned = sum(it.planned_count for t in tasks_by_day[d] for it in t.book_items)
        completed = sum(it.completed_count for t in tasks_by_day[d] for it in t.book_items)
        day_summary[d] = {
            "planned": planned,
            "completed": completed,
            "tasks": len(tasks_by_day[d]),
            "pct": int(round(100 * completed / planned)) if planned > 0 else 0,
        }

    week_planned = sum(s["planned"] for s in day_summary.values())
    week_completed = sum(s["completed"] for s in day_summary.values())
    week_pct = int(round(100 * week_completed / week_planned)) if week_planned > 0 else 0

    # Ders bazında bu haftanın kırılımı
    subject_totals = {}
    for t in tasks:
        for it in t.book_items:
            sid = it.book.subject_id
            entry = subject_totals.setdefault(
                sid,
                {"name": it.book.subject.name, "planned": 0, "completed": 0},
            )
            entry["planned"] += it.planned_count
            entry["completed"] += it.completed_count
    subject_rows = [
        {**v, "pct": int(round(100 * v["completed"] / v["planned"])) if v["planned"] > 0 else 0}
        for v in subject_totals.values()
    ]
    subject_rows.sort(key=lambda r: -r["planned"])

    snapshot = student_snapshot(db, user, today=date.today())

    academic_year = None
    if user.academic_year_id:
        from app.models import AcademicYear
        academic_year = db.query(AcademicYear).filter(AcademicYear.id == user.academic_year_id).first()

    return templates.TemplateResponse(
        "student/weekly_report_print.html",
        {
            "request": request,
            "user": user,
            "student": user,
            "academic_year": academic_year,
            "start": start,
            "end": end,
            "days": days,
            "tasks_by_day": tasks_by_day,
            "day_summary": day_summary,
            "week_planned": week_planned,
            "week_completed": week_completed,
            "week_pct": week_pct,
            "subject_rows": subject_rows,
            "snapshot": snapshot,
            "projection": snapshot.projection,
            "tr_weekdays": TR_WEEKDAYS,
            "tr_months": TR_MONTHS,
            "today": date.today(),
        },
    )


@router.get("/books-by-subject")
def student_cascade_books(
    request: Request,
    subject_id: str = Query(""),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    parsed: int | None = None
    if subject_id.strip():
        try:
            parsed = int(subject_id)
        except ValueError:
            parsed = None
    assignments = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(StudentBook.student_id == user.id)
        .all()
    )
    books = []
    for sb in assignments:
        if parsed is None or sb.book.subject_id == parsed:
            books.append({"id": sb.book.id, "name": sb.book.name})
    books.sort(key=lambda b: b["name"])
    return templates.TemplateResponse(
        "teacher/partials/books_options.html",
        {"request": request, "books": books, "subject_id": parsed},
    )


@router.get("/book-grid")
def student_book_grid(
    request: Request,
    book_id: int = Query(...),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Sinema-koltuk grid (öğrenci tarafı) — kendi kitap görünümü."""
    sb = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == user.id, StudentBook.book_id == book_id)
        .first()
    )
    if not sb:
        raise HTTPException(status_code=404, detail="Bu kitap size atanmamış")
    pmap = {p.book_section_id: p for p in sb.section_progress}
    sections_data = []
    total_completed = 0
    total_reserved = 0
    for sec in sb.book.sections:
        sp = pmap.get(sec.id)
        completed = sp.completed_count if sp else 0
        reserved = sp.reserved_count if sp else 0
        sections_data.append({"section": sec, "completed": completed, "reserved": reserved})
        total_completed += completed
        total_reserved += reserved
    return templates.TemplateResponse(
        "teacher/partials/book_grid_content.html",
        {
            "request": request,
            "book": sb.book,
            "sections_data": sections_data,
            "total_completed": total_completed,
            "total_reserved": total_reserved,
        },
    )


@router.get("/book-sections")
def student_cascade_sections(
    request: Request,
    book_id: int = Query(...),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    sb = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == user.id, StudentBook.book_id == book_id)
        .first()
    )
    if not sb:
        return templates.TemplateResponse(
            "teacher/partials/sections_options.html",
            {"request": request, "sections": []},
        )
    pmap = {p.book_section_id: p for p in sb.section_progress}
    items = []
    for sec in sb.book.sections:
        sp = pmap.get(sec.id)
        res = sp.reserved_count if sp else 0
        done = sp.completed_count if sp else 0
        remaining = sec.test_count - res - done
        items.append({
            "id": sec.id,
            "label": sec.label,
            "topic": sec.topic.name if sec.topic else None,
            "remaining": remaining,
            "total": sec.test_count,
        })
    return templates.TemplateResponse(
        "teacher/partials/sections_options.html",
        {
            "request": request,
            "sections": items,
            "is_deneme": sb.book.type.value in ("brans_denemesi", "genel_deneme"),
        },
    )


@router.get("/week/print")
def student_week_print(
    request: Request,
    start_param: str | None = Query(None, alias="start"),
    date_param: str | None = Query(None, alias="date"),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """A4 için optimize edilmiş haftalık yazdırma sayfası."""
    raw = start_param or date_param
    try:
        start = date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        start = date.today()
    days = [start + timedelta(days=i) for i in range(7)]
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == user.id, Task.date.in_(days))
        .order_by(Task.date, Task.order, Task.id)
        .all()
    )
    tasks_by_day = {d: [] for d in days}
    for t in tasks:
        tasks_by_day[t.date].append(t)

    # Academic year (opsiyonel)
    academic_year = None
    if user.academic_year_id:
        from app.models import AcademicYear
        academic_year = db.query(AcademicYear).filter(AcademicYear.id == user.academic_year_id).first()

    return templates.TemplateResponse(
        "student/week_print.html",
        {
            "request": request,
            "user": user,
            "student": user,
            "academic_year": academic_year,
            "start": start,
            "end": days[-1],
            "days": days,
            "tasks_by_day": tasks_by_day,
            "tr_weekdays": TR_WEEKDAYS,
            "tr_months": TR_MONTHS,
        },
    )


@router.get("/books")
def student_books(
    request: Request,
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    ctx = _student_book_progress_map(db, user.id)
    total = sum(sum(sb.total_tests for sb in sbs) for sbs in ctx["assignments_by_subject"].values())
    completed = sum(sum(sb.completed_tests for sb in sbs) for sbs in ctx["assignments_by_subject"].values())
    reserved = sum(sum(sb.reserved_tests for sb in sbs) for sbs in ctx["assignments_by_subject"].values())
    return templates.TemplateResponse(
        "student/books.html",
        {
            "request": request,
            "user": user,
            "student": user,
            "total_tests": total,
            "completed": completed,
            "reserved": reserved,
            "remaining": total - completed - reserved,
            **ctx,
        },
    )


def _get_own_task(db: Session, task_id: int, student_id: int) -> Task:
    task = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.id == task_id, Task.student_id == student_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    return task


def _ensure_not_future(task: Task) -> None:
    """Gelecek tarihli görevin tıklanmasını engelle."""
    if task.date > date.today():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Bu görev {task.date.strftime('%d.%m.%Y')} tarihli — gelecek bir günü "
                "tıklayamazsın. O gün gelince tikleyebilirsin."
            ),
        )


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    request: Request,
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = _get_own_task(db, task_id, user.id)
    _ensure_not_future(task)
    try:
        svc_complete_task(db, task)
    except ReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    # Görev COMPLETED'a geçti → döngü-son kontrolü; commit'ten önce ki aynı transaction
    _fire_task_completed_event(db, user)
    db.commit()
    db.refresh(task)
    return _htmx_task_update(request, db, user, task)


@router.post("/tasks/{task_id}/uncomplete")
def uncomplete_task(
    task_id: int,
    request: Request,
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = _get_own_task(db, task_id, user.id)
    # uncomplete'ta gelecek bloğu yok — geçmişteki yanlış tikleri geri almak için izin ver
    svc_uncomplete_task(db, task)
    db.commit()
    db.refresh(task)
    return _htmx_task_update(request, db, user, task)


@router.post("/tasks/{task_id}/items/{item_id}/set-completed")
def set_item_completed(
    task_id: int,
    item_id: int,
    request: Request,
    completed: int = Form(...),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = _get_own_task(db, task_id, user.id)
    _ensure_not_future(task)
    item = next((i for i in task.book_items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404)
    try:
        set_item_completion(db, item, completed)
    except ReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    # Görev durumunu yeniden değerlendir
    total_planned = sum(i.planned_count for i in task.book_items)
    total_done = sum(i.completed_count for i in task.book_items)
    if total_done == 0:
        task.status = TaskStatus.PENDING
        task.completed_at = None
    elif total_done >= total_planned:
        from datetime import datetime, timezone
        previously_completed = task.status == TaskStatus.COMPLETED
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        # Sadece yeni COMPLETED'a geçtiyse event fırlat (tekrar tetikleme yok)
        if not previously_completed:
            _fire_task_completed_event(db, user)
    else:
        task.status = TaskStatus.PARTIAL
        task.completed_at = None
    db.commit()
    db.refresh(task)
    return _htmx_task_update(request, db, user, task)


def _htmx_task_update(request: Request, db: Session, user: User, task: Task):
    """HTMX yanıtı: görev kartı + sidebar OOB + günlük özet OOB."""
    ctx = _student_book_progress_map(db, user.id)
    # Günlük özet yeniden hesapla
    day_tasks = _load_day_tasks(db, user.id, task.date)
    total_items = sum(len(t.book_items) for t in day_tasks)
    planned = sum(it.planned_count for t in day_tasks for it in t.book_items)
    completed = sum(it.completed_count for t in day_tasks for it in t.book_items)
    # task_card → task_comm_modal task_max_counts'a ihtiyaç duyar
    from app.services.request_service import max_new_count_for_change
    task_max_counts: dict[int, int] = {}
    if len(task.book_items) == 1:
        try:
            task_max_counts[task.id] = max_new_count_for_change(db, task, task.book_items[0])
        except Exception:
            task_max_counts[task.id] = task.book_items[0].planned_count
    # Modal cascade için: ders listesi
    subjects_set = {}
    for sb in ctx["assignments"]:
        subjects_set[sb.book.subject.id] = sb.book.subject
    subject_list = sorted(subjects_set.values(), key=lambda s: (s.order, s.name))
    return templates.TemplateResponse(
        "student/partials/task_update_response.html",
        {
            "request": request,
            "user": user,
            "student": user,
            "task": task,
            "total_items": total_items,
            "planned_count": planned,
            "completed_count": completed,
            "task_max_counts": task_max_counts,
            "subject_list": subject_list,
            **ctx,
        },
    )
