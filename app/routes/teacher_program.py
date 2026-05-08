from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
    TaskType,
    User,
    UserRole,
)
from app.services.event_triggers import on_program_published
from app.services.suggestions import (
    build_student_model,
    confidence_label,
    maturity,
    maturity_label,
    suggest_for_date,
)
from app.templating import templates

router = APIRouter(prefix="/teacher/students")


TR_WEEKDAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


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


def compute_day_subject_summary(
    day_tasks: list, subjects: list,
) -> list[dict]:
    """Bir günün görevlerini derslere göre özetler.

    subjects: öğrencinin atanmış kitabı olan tüm dersler (sıralı).
    Dönüş: subjects sırasında, her ders için {subject, task_count, tests, denemeler}.
    Hiç görev olmayan ders de listede olur (task_count=0).
    """
    by_sid: dict[int, dict] = {}
    for t in day_tasks:
        for it in t.book_items:
            sid = it.book.subject_id
            is_deneme = it.book.type.value in ("brans_denemesi", "genel_deneme")
            entry = by_sid.setdefault(
                sid, {"task_ids": set(), "tests": 0, "denemeler": 0}
            )
            entry["task_ids"].add(t.id)
            if is_deneme:
                entry["denemeler"] += it.planned_count
            else:
                entry["tests"] += it.planned_count

    out = []
    for subj in subjects:
        e = by_sid.get(subj.id)
        out.append({
            "subject": subj,
            "task_count": len(e["task_ids"]) if e else 0,
            "tests": e["tests"] if e else 0,
            "denemeler": e["denemeler"] if e else 0,
        })
    return out


def build_day_card_context(db: Session, student: User, day: date) -> dict:
    """Tek bir gün için day_card.html partial'ının ihtiyaç duyduğu tüm bağlamı üret.

    HTMX swap eden POST handler'ları ve fragment endpoint birlikte kullanır.
    """
    today = date.today()

    # Bu güne ait görevler (book_items + book/section + topic ile)
    day_tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == student.id, Task.date == day)
        .order_by(Task.order, Task.id)
        .all()
    )
    # Aynı dersler alt alta: birincil ders (ilk book_item'ın dersi) ve sonra orijinal sıra
    day_tasks.sort(
        key=lambda t: (
            (t.book_items[0].book.subject.order, t.book_items[0].book.subject.id)
            if t.book_items else (10**9, 10**9),
            t.order,
            t.id,
        )
    )
    planned_total = sum(it.planned_count for t in day_tasks for it in t.book_items)

    # Öğrencinin kitap envanteri (form için)
    assignments = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    subjects_map = {}
    for sb in assignments:
        subjects_map[sb.book.subject.id] = sb.book.subject
    subjects = sorted(subjects_map.values(), key=lambda s: (s.order, s.name))

    # Öneri motoru — sadece bu gün için
    student_model = build_student_model(db, student.id)
    mat = maturity(student_model)
    exclude = {
        (it.book_id, it.book_section_id) for t in day_tasks for it in t.book_items
    }
    day_suggestions = suggest_for_date(
        db, student.id, day, model=student_model, exclude_keys=exclude
    )

    # Bu güne ait dersler bazında özet
    day_subject_summary = compute_day_subject_summary(day_tasks, subjects)

    return {
        "day": day,
        "day_tasks": day_tasks,
        "is_today": day == today,
        "planned_total": planned_total,
        "day_suggestions": day_suggestions,
        "student": student,
        "assignments": assignments,
        "subjects": subjects,
        "day_subject_summary": day_subject_summary,
        "task_types": list(TaskType),
        "tr_weekdays": TR_WEEKDAYS,
        "tr_months": TR_MONTHS,
        "maturity_value": mat,
        "maturity_label": maturity_label(mat),
        "weeks_observed": student_model.weeks_observed,
        "days_observed": student_model.days_observed,
        "confidence_label": confidence_label,
    }


@router.get("/{student_id}/week")
def week_view(
    student_id: int,
    request: Request,
    start_param: str | None = Query(None, alias="start"),
    date_param: str | None = Query(None, alias="date"),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """7 günlük program penceresi.

    Varsayılan: bugünden başlayan 7 gün.
    `?start=YYYY-MM-DD` (veya eski `?date=YYYY-MM-DD`) pencerenin ilk gününü belirler.
    Önceki/Sonraki navigasyonu bu başlangıcı ±7 gün kaydırır.
    """
    student = _ensure_student(db, user.id, student_id)
    raw = start_param or date_param
    try:
        start = date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        start = date.today()
    days = [start + timedelta(days=i) for i in range(7)]
    end = days[-1]

    # Haftadaki tüm görevler (+ kalemleri + ilgili kitap/bölüm)
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == student.id, Task.date.in_(days))
        .order_by(Task.date, Task.order, Task.id)
        .all()
    )
    tasks_by_day: dict[date, list[Task]] = {d: [] for d in days}
    for t in tasks:
        tasks_by_day[t.date].append(t)
    # Her gün içinde, aynı dersler alt alta gelsin (birincil dersin order/id'sine göre)
    for d in days:
        tasks_by_day[d].sort(
            key=lambda t: (
                (t.book_items[0].book.subject.order, t.book_items[0].book.subject.id)
                if t.book_items else (10**9, 10**9),
                t.order,
                t.id,
            )
        )

    # Her gün için planlanan toplam test adedi (tüm kalemlerin planned_count toplamı)
    day_planned_totals: dict[date, int] = {
        d: sum(it.planned_count for t in tasks_by_day[d] for it in t.book_items)
        for d in days
    }

    # Her gün için ders bazında görev özeti (subjects yukarıda hazır)
    # NOT: subjects, assignments_by_subject hesaplandıktan sonra dolduracağız.

    # Görev formu için: öğrenciye atanmış kitaplar + her kitabın bölümleri + kalan kapasiteleri
    assignments = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    # section remaining map: section_id -> remaining
    remaining_by_section: dict[int, int] = {}
    for sb in assignments:
        pmap = {p.book_section_id: p for p in sb.section_progress}
        for sec in sb.book.sections:
            sp = pmap.get(sec.id)
            res = sp.reserved_count if sp else 0
            done = sp.completed_count if sp else 0
            remaining_by_section[sec.id] = sec.test_count - res - done

    # Öneri motoru — request başına 1 kez öğrenme modeli kurup her güne uygula
    student_model = build_student_model(db, student.id)
    mat = maturity(student_model)
    suggestions_by_day: dict[date, list] = {}
    for d in days:
        exclude = {(it.book_id, it.book_section_id) for t in tasks_by_day[d] for it in t.book_items}
        suggestions_by_day[d] = suggest_for_date(
            db, student.id, d, model=student_model, exclude_keys=exclude
        )

    # Sadece atanmış kitabı olan dersler listelensin; ders-kitap gruplaması + ders toplamları
    subjects_map = {}
    assignments_by_subject: dict[int, list[StudentBook]] = {}
    for sb in assignments:
        sid = sb.book.subject.id
        subjects_map[sid] = sb.book.subject
        assignments_by_subject.setdefault(sid, []).append(sb)
    subjects = sorted(subjects_map.values(), key=lambda s: (s.order, s.name))
    subject_summary: dict[int, dict[str, int]] = {}
    for sid, sbs in assignments_by_subject.items():
        total = sum(sb.total_tests for sb in sbs)
        completed = sum(sb.completed_tests for sb in sbs)
        reserved = sum(sb.reserved_tests for sb in sbs)
        subject_summary[sid] = {
            "total": total,
            "completed": completed,
            "reserved": reserved,
            "remaining": total - completed - reserved,
            "books": len(sbs),
        }

    # Per-day subject summary (subjects hesaplandıktan sonra)
    day_subject_summary_by_day: dict[date, list[dict]] = {
        d: compute_day_subject_summary(tasks_by_day[d], subjects) for d in days
    }

    return templates.TemplateResponse(
        "teacher/student_week.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "start": start,
            "end": end,
            "days": days,
            "today": date.today(),
            "tasks_by_day": tasks_by_day,
            "day_planned_totals": day_planned_totals,
            "day_subject_summary_by_day": day_subject_summary_by_day,
            "prev_date": (start - timedelta(days=7)).isoformat(),
            "next_date": (start + timedelta(days=7)).isoformat(),
            "tr_weekdays": TR_WEEKDAYS,
            "tr_months": TR_MONTHS,
            "assignments": assignments,
            "subjects": subjects,
            "assignments_by_subject": assignments_by_subject,
            "subject_summary": subject_summary,
            "remaining_by_section": remaining_by_section,
            "task_types": list(TaskType),
            "suggestions_by_day": suggestions_by_day,
            "maturity_value": mat,
            "maturity_label": maturity_label(mat),
            "weeks_observed": student_model.weeks_observed,
            "days_observed": student_model.days_observed,
            "confidence_label": confidence_label,
        },
    )


@router.get("/{student_id}/week/day-card")
def day_card_fragment(
    student_id: int,
    request: Request,
    date_param: str = Query(..., alias="date"),
    keep_open: str = Query(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """HTMX fragment — tek bir günün tam day-card render'ı."""
    student = _ensure_student(db, user.id, student_id)
    try:
        target = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")
    ctx = build_day_card_context(db, student, target)
    return templates.TemplateResponse(
        "teacher/partials/day_card.html",
        {"request": request, "user": user, "keep_open": keep_open or None, **ctx},
    )


def _build_sidebar_context(
    db: Session, student_id: int, focused_subject_id: int | None
) -> dict:
    """Kaynak Durumu sidebar'ı için bağlam üret — isteğe göre derse filtrele."""
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
    if focused_subject_id is not None:
        assignments = [sb for sb in assignments if sb.book.subject_id == focused_subject_id]

    subjects_map = {}
    assignments_by_subject: dict[int, list[StudentBook]] = {}
    for sb in assignments:
        sid = sb.book.subject.id
        subjects_map[sid] = sb.book.subject
        assignments_by_subject.setdefault(sid, []).append(sb)
    subjects = sorted(subjects_map.values(), key=lambda s: (s.order, s.name))
    subject_summary: dict[int, dict[str, int]] = {}
    for sid, sbs in assignments_by_subject.items():
        total = sum(sb.total_tests for sb in sbs)
        completed = sum(sb.completed_tests for sb in sbs)
        reserved = sum(sb.reserved_tests for sb in sbs)
        subject_summary[sid] = {
            "total": total,
            "completed": completed,
            "reserved": reserved,
            "remaining": total - completed - reserved,
            "books": len(sbs),
        }
    return {
        "subjects": subjects,
        "assignments_by_subject": assignments_by_subject,
        "subject_summary": subject_summary,
        "focused_subject_id": focused_subject_id,
    }


@router.get("/{student_id}/books-by-subject")
def books_by_subject_fragment(
    student_id: int,
    request: Request,
    subject_id: str = Query(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """HTMX fragment — seçilen derse ait, öğrenciye atanmış kitap seçenekleri.

    Sadece <option> tag'leri döner (parsing güvenliği için OOB div karıştırma).
    Sidebar filtresi side-effect'i HX-Trigger header'ı ile yapılır; sayfa
    document.body üzerinde 'subject-changed' event'ini dinleyip sidebar'ı yeniler.
    """
    import json
    from fastapi.responses import HTMLResponse

    _ensure_student(db, user.id, student_id)
    parsed_subject: int | None = None
    if subject_id.strip():
        try:
            parsed_subject = int(subject_id)
        except ValueError:
            parsed_subject = None

    assignments = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(StudentBook.student_id == student_id)
        .all()
    )
    books = []
    for sb in assignments:
        if parsed_subject is None or sb.book.subject_id == parsed_subject:
            books.append({"id": sb.book.id, "name": sb.book.name})
    books.sort(key=lambda b: b["name"])

    response = templates.TemplateResponse(
        "teacher/partials/books_options.html",
        {
            "request": request,
            "books": books,
            "subject_id": parsed_subject,
        },
    )
    # Sidebar filter side-effect — page'deki listener subject-changed event'ini yakalar
    response.headers["HX-Trigger"] = json.dumps({
        "subject-changed": {"subject_id": str(parsed_subject) if parsed_subject is not None else ""}
    })
    return response


@router.get("/{student_id}/sidebar-items")
def sidebar_items_fragment(
    student_id: int,
    request: Request,
    subject_id: str = Query(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """HTMX fragment — Kaynak Durumu sidebar içeriği (tümü veya tek derse filtreli)."""
    student = _ensure_student(db, user.id, student_id)
    focused: int | None = None
    if subject_id.strip():
        try:
            focused = int(subject_id)
        except ValueError:
            focused = None
    ctx = _build_sidebar_context(db, student_id, focused)
    return templates.TemplateResponse(
        "teacher/partials/resource_sidebar_items.html",
        {"request": request, "user": user, "student": student, **ctx},
    )


@router.get("/{student_id}/book-grid")
def book_grid_modal(
    student_id: int,
    request: Request,
    book_id: int = Query(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Bir kitabın 'sinema koltuğu' tarzı grid görünümü (HTMX modal içeriği)."""
    _ensure_student(db, user.id, student_id)
    sb = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student_id, StudentBook.book_id == book_id)
        .first()
    )
    if not sb:
        raise HTTPException(status_code=404, detail="Kitap bu öğrenciye atanmamış")
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


@router.get("/{student_id}/book-sections")
def book_sections_fragment(
    student_id: int,
    request: Request,
    book_id: int = Query(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """HTMX fragment — seçilen kitabın bölüm (ünite/deneme) seçenekleri."""
    _ensure_student(db, user.id, student_id)
    sb = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student_id, StudentBook.book_id == book_id)
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
        items.append({"id": sec.id, "label": sec.label, "topic": sec.topic.name if sec.topic else None, "remaining": remaining, "total": sec.test_count})
    return templates.TemplateResponse(
        "teacher/partials/sections_options.html",
        {"request": request, "sections": items, "is_deneme": sb.book.type.value in ("brans_denemesi", "genel_deneme")},
    )


@router.post("/{student_id}/program/notify-parents")
def notify_parents_program(
    student_id: int,
    request: Request,
    start: str = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """"Programı veliye duyur" — pencerenin başlangıç tarihinden 7 günlük programı
    NEW_PROGRAM bildirimi olarak ilgili velilere kuyruğa atar.

    Dedup: 24 saat içinde aynı öğrenci için NEW_PROGRAM gönderilmişse atlanır.
    Tetikleme yalnızca öğrencinin gerçekten görevi olan bir hafta için anlamlı —
    program boşsa no-op.
    """
    student = _ensure_student(db, user.id, student_id)
    try:
        week_start = date.fromisoformat(start)
    except ValueError:
        msg = "Geçersiz tarih."
        return RedirectResponse(
            url=f"/teacher/students/{student_id}/week?err={quote(msg)}",
            status_code=303,
        )

    summary = on_program_published(db, student=student, week_start=week_start)
    db.commit()

    if summary.get("no_tasks"):
        msg = "Bu hafta için görev bulunmuyor; veliye duyuru gönderilmedi."
        return RedirectResponse(
            url=f"/teacher/students/{student_id}/week?start={start}&err={quote(msg)}",
            status_code=303,
        )

    fired = summary.get("fired", 0)
    skipped = summary.get("skipped_recent", 0)
    if fired == 0 and skipped > 0:
        msg = (
            "Velilere son 24 saat içinde aynı program duyuruldu — yeniden "
            "gönderilmedi."
        )
    elif fired == 0:
        msg = "Bağlı veli bulunamadı; duyuru yapılmadı."
    else:
        suffix = f" ({skipped} veli son 24 saat içinde duyurulmuş, atlandı)" if skipped else ""
        msg = f"Program {fired} veliye duyuruldu.{suffix}"

    return RedirectResponse(
        url=f"/teacher/students/{student_id}/week?start={start}&ok={quote(msg)}",
        status_code=303,
    )
