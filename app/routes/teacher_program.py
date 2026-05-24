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
    WeekNote,
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


def _resolve_week_anchor(db: Session, student: User) -> date | None:
    """Öğrencinin hafta anchor'ını çözer. Sıra:
    1) user.program_anchor_date (öğretmen manuel ayarladıysa)
    2) en eski Task.date (otomatik)
    3) None (hiç görev yok)
    """
    if getattr(student, "program_anchor_date", None):
        return student.program_anchor_date
    anchor_row = (
        db.query(Task.date)
        .filter(Task.student_id == student.id)
        .order_by(Task.date.asc())
        .first()
    )
    return anchor_row[0] if anchor_row else None


def _student_week_start(db: Session, student: User, target: date) -> date:
    """`target`'i içeren, öğrenciye özel 7-günlük bloğun ilk gününü döndürür.

    Anchor sırası: `user.program_anchor_date` → en eski Task.date → bugünün
    Pazartesi'si. Mantık: anchor'dan target'a kaç tam 7-günlük blok geçtiyse
    o blok başlar (Python floor division negatif tarafa da doğru çeker).
    Örn anchor=24.04 Cuma → bloklar [24.04, 01.05, 08.05, 15.05, 22.05, ...].
    target=17.05 → blok = 15.05 (Cuma), pencere 15-21.05.
    """
    anchor = _resolve_week_anchor(db, student)
    if anchor is None:
        return target - timedelta(days=target.weekday())
    block = (target - anchor).days // 7
    return anchor + timedelta(days=block * 7)


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
            if it.book is None:
                continue  # kitapsız deneme kalemi — derse bağlı değil, ders özetine girmez
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
    # Sıralama: scheduled_hour (NULLS LAST) → ders → manuel order → id.
    # Saat atanmışsa kronolojik; değilse ders bazında alt alta (eski davranış).
    day_tasks.sort(
        key=lambda t: (
            0 if t.scheduled_hour is not None else 1,
            t.scheduled_hour if t.scheduled_hour is not None else 0,
            (t.book_items[0].book.subject.order, t.book_items[0].book.subject.id)
            if t.book_items else (10**9, 10**9),
            t.order,
            t.id,
        )
    )
    planned_total = sum(it.planned_count for t in day_tasks for it in t.book_items)
    day_draft_count = sum(1 for t in day_tasks if t.is_draft)

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
        "day_draft_count": day_draft_count,
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
    if raw:
        try:
            start = date.fromisoformat(raw)
        except ValueError:
            # Geçersiz parametre: öğrencinin bugünkü haftasına düş
            start = _student_week_start(db, student, date.today())
    else:
        # Default: bugünü içeren öğrenci-haftası bloğunun başı.
        # Anchor = öğrencinin en eski Task.date'i. Görev yoksa Pazartesi.
        start = _student_week_start(db, student, date.today())
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
    # Sıralama: önce scheduled_hour (NULLS LAST), sonra ders sırası, sonra manuel order/id.
    # Saat atanmış görevler önce gelir (gün boyu kronolojik); saatsizler ders bazında dipten.
    for d in days:
        tasks_by_day[d].sort(
            key=lambda t: (
                0 if t.scheduled_hour is not None else 1,
                t.scheduled_hour if t.scheduled_hour is not None else 0,
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

    # Gün bazında taslak sayısı + tüm hafta toplam taslak
    day_draft_counts: dict[date, int] = {
        d: sum(1 for t in tasks_by_day[d] if t.is_draft) for d in days
    }
    week_draft_total = sum(day_draft_counts.values())

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

    # Anchor görünürlüğü: kullanıcıya "şu an hangi anchor'a göre 7'lik bloklar
    # yürüyor" göster. None ise "anchor yok, ISO Pazartesi" anlamına gelir.
    week_anchor = _resolve_week_anchor(db, student)
    anchor_is_manual = student.program_anchor_date is not None

    # Hafta notları (madde madde) — bu pencerenin start'ına bağlı
    week_notes = _load_week_notes(db, student.id, start)

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
            "week_anchor": week_anchor,
            "anchor_is_manual": anchor_is_manual,
            "week_notes": week_notes,
            "tasks_by_day": tasks_by_day,
            "day_planned_totals": day_planned_totals,
            "day_draft_counts": day_draft_counts,
            "week_draft_total": week_draft_total,
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


def _load_week_notes(db: Session, student_id: int, week_start: date) -> list[WeekNote]:
    return (
        db.query(WeekNote)
        .filter(WeekNote.student_id == student_id, WeekNote.week_start == week_start)
        .order_by(WeekNote.order.asc(), WeekNote.id.asc())
        .all()
    )


def _render_week_notes_partial(
    request: Request, db: Session, student: User, week_start: date,
):
    notes = _load_week_notes(db, student.id, week_start)
    return templates.TemplateResponse(
        "teacher/partials/week_notes_card.html",
        {
            "request": request,
            "student": student,
            "week_start": week_start,
            "notes": notes,
        },
    )


@router.get("/{student_id}/week-notes")
def week_notes_fragment(
    student_id: int,
    request: Request,
    week_start: str = Query(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = _ensure_student(db, user.id, student_id)
    try:
        ws = date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")
    return _render_week_notes_partial(request, db, student, ws)


@router.post("/{student_id}/week-notes/add")
def week_notes_add(
    student_id: int,
    request: Request,
    week_start: str = Form(...),
    body: str = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = _ensure_student(db, user.id, student_id)
    body = body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Not metni boş olamaz")
    try:
        ws = date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih")
    existing = _load_week_notes(db, student.id, ws)
    next_order = (existing[-1].order + 1) if existing else 0
    db.add(WeekNote(
        student_id=student.id,
        week_start=ws,
        body=body,
        order=next_order,
    ))
    db.commit()
    return _render_week_notes_partial(request, db, student, ws)


@router.post("/{student_id}/week-notes/{note_id}/delete")
def week_notes_delete(
    student_id: int,
    note_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = _ensure_student(db, user.id, student_id)
    note = (
        db.query(WeekNote)
        .filter(WeekNote.id == note_id, WeekNote.student_id == student.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404)
    ws = note.week_start
    db.delete(note)
    db.commit()
    return _render_week_notes_partial(request, db, student, ws)


@router.post("/{student_id}/week-notes/{note_id}/toggle")
def week_notes_toggle(
    student_id: int,
    note_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = _ensure_student(db, user.id, student_id)
    note = (
        db.query(WeekNote)
        .filter(WeekNote.id == note_id, WeekNote.student_id == student.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404)
    note.is_done = not note.is_done
    db.commit()
    return _render_week_notes_partial(request, db, student, note.week_start)


@router.post("/{student_id}/set-week-anchor")
def set_week_anchor(
    student_id: int,
    anchor: str = Form(...),
    return_to: str = Form("week"),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin hafta anchor'ını manuel ayarla. Koçluk günü değişince
    haftalık bloklar buradan kayar. `anchor='clear'` ile manuel anchor
    silinir → fallback (en eski Task tarihi) devreye girer.

    return_to: 'week' (default) → haftalık view'a yeni bloğa git;
               'detail' → öğrenci detay sayfasının coaching tab'ına dön.
    """
    student = _ensure_student(db, user.id, student_id)
    if anchor.strip().lower() == "clear":
        student.program_anchor_date = None
    else:
        try:
            student.program_anchor_date = date.fromisoformat(anchor)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih")
    db.commit()
    if return_to == "detail":
        return RedirectResponse(
            url=f"/teacher/students/{student.id}#overview",
            status_code=303,
        )
    # Default: pencereyi yeni anchor'ın bugünü içerdiği bloğa götür
    new_start = _student_week_start(db, student, date.today())
    return RedirectResponse(
        url=f"/teacher/students/{student.id}/week?start={new_start.isoformat()}",
        status_code=303,
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


def _build_slot_url(iso_date: str, task_id: int, *, teacher_student_id: int | None) -> str:
    """Sinema-koltuk kutusu için hedef URL: o günün Pazartesi'sinden başlayan
    hafta penceresi + ilgili task anchor'ı. Öğretmen ve öğrenci paneli için ayrı.
    """
    d = date.fromisoformat(iso_date)
    monday = (d - timedelta(days=d.weekday())).isoformat()
    if teacher_student_id is not None:
        return f"/teacher/students/{teacher_student_id}/week?start={monday}#task-{task_id}"
    # Öğrenci tarafı: gün view'ı zaten tek gün gösteriyor
    return f"/student/day?date={iso_date}#task-{task_id}"


def build_book_grid_slots(
    db: Session,
    student_id: int,
    section_ids: list[int],
    *,
    teacher_student_id: int | None = None,
) -> dict[int, dict]:
    """Section ID -> {"completed": [...], "reserved": [...]}.

    Her slot: {date: 'YYYY-MM-DD', label: 'dd.mm.yyyy', task_id: int, url: str}.
    Tarihe göre sıralı; aynı task içinde önce completed slot'lar, sonra rezerve.
    Cinema-seat'in n'inci kutucuğunun hangi göreve / tarihe ait olduğunu ve
    hedef hafta+anchor URL'sini taşır.

    teacher_student_id: None ise öğrenci tarafı URL'si üretilir;
    aksi halde öğretmen panelinin haftalık görüntüsü için URL üretilir.
    """
    out: dict[int, dict] = {sid: {"completed": [], "reserved": []} for sid in section_ids}
    if not section_ids:
        return out
    rows = (
        db.query(
            TaskBookItem.book_section_id,
            TaskBookItem.planned_count,
            TaskBookItem.completed_count,
            Task.id,
            Task.date,
        )
        .join(Task, TaskBookItem.task_id == Task.id)
        .filter(
            Task.student_id == student_id,
            TaskBookItem.book_section_id.in_(section_ids),
            Task.is_draft.is_(False),
        )
        .order_by(Task.date.asc(), Task.id.asc())
        .all()
    )
    for sid, planned_n, completed_n, tid, tdate in rows:
        if sid not in out:
            continue
        iso = tdate.isoformat()
        label = tdate.strftime("%d.%m.%Y")
        url = _build_slot_url(iso, tid, teacher_student_id=teacher_student_id)
        for _ in range(completed_n or 0):
            out[sid]["completed"].append({
                "date": iso, "label": label, "task_id": tid, "url": url,
            })
        remaining = max(0, (planned_n or 0) - (completed_n or 0))
        for _ in range(remaining):
            out[sid]["reserved"].append({
                "date": iso, "label": label, "task_id": tid, "url": url,
            })
    return out


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
    section_ids = [sec.id for sec in sb.book.sections]
    slots_map = build_book_grid_slots(
        db, student_id, section_ids, teacher_student_id=student_id,
    )
    sections_data = []
    total_completed = 0
    total_reserved = 0
    for sec in sb.book.sections:
        sp = pmap.get(sec.id)
        completed = sp.completed_count if sp else 0
        reserved = sp.reserved_count if sp else 0
        sections_data.append({
            "section": sec,
            "completed": completed,
            "reserved": reserved,
            "slots": slots_map.get(sec.id, {"completed": [], "reserved": []}),
        })
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


@router.get("/{student_id}/section-stats")
def section_stats_fragment(
    student_id: int,
    request: Request,
    section_id: int = Query(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """HTMX fragment — seçilen bölümün test yükü kartları (Bölümde / Çözülmüş / Kalan).

    Görev ekleme formunda Ünite/Deneme seçildiğinde tetiklenir; öğretmen
    o bölümde kaç test olduğunu, kaçının çözüldüğünü ve kaçının kaldığını
    görsel olarak görsün diye.
    """
    _ensure_student(db, user.id, student_id)
    sec = (
        db.query(BookSection)
        .options(joinedload(BookSection.topic), joinedload(BookSection.book))
        .filter(BookSection.id == section_id)
        .first()
    )
    if not sec:
        return templates.TemplateResponse(
            "teacher/partials/section_stats.html",
            {"request": request, "section": None},
        )
    sb = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.section_progress))
        .filter(StudentBook.student_id == student_id, StudentBook.book_id == sec.book_id)
        .first()
    )
    completed = 0
    reserved = 0
    if sb:
        for sp in sb.section_progress:
            if sp.book_section_id == sec.id:
                completed = sp.completed_count
                reserved = sp.reserved_count
                break
    total = sec.test_count
    remaining = max(0, total - completed - reserved)
    return templates.TemplateResponse(
        "teacher/partials/section_stats.html",
        {
            "request": request,
            "section": sec,
            "total": total,
            "completed": completed,
            "reserved": reserved,
            "remaining": remaining,
        },
    )


@router.get("/{student_id}/review-struggle-suggestions")
def review_struggle_suggestions(
    student_id: int,
    request: Request,
    subject_id: int = Query(...),
    target_date: str = Query(..., alias="target_date"),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """HTMX fragment — Tekrar tipi seçildi + ders seçildiğinde FSRS'ten gelen öneri chip'leri.

    Filtreler:
      - Sadece bu öğrencinin kartları
      - Sadece bu derse ait topic'ler
      - Sadece **vadesi gelmiş** kartlar (due_at <= target_date, gün bazında)
      - Minimum zorlanma skoru (>=10) — sıradan kartlarla öğretmeni yormamak için
      - Skor azalan sırada en fazla 8 öneri

    target_date günlük programdaki ilgili günün tarihi. Bu gün için tekrar
    görevi planlanırken sadece "bugün gösterilmesi gereken kart"ları sunuyoruz.
    """
    from datetime import datetime, time, timezone, timedelta
    from app.models.review import ReviewCard
    from app.models.curriculum import Topic
    from app.services.review_scheduler import _struggle_score
    from app.services.study_dna import TR_OFFSET_HOURS

    _ensure_student(db, user.id, student_id)
    try:
        td = date.fromisoformat(target_date)
    except ValueError:
        td = date.today()

    # Target günün TR sonu (UTC'ye çevir): kartın due_at değeri bu sınırı geçmiyorsa
    # "bugün için vadesi geldi" sayılır (yarın için yapılan plan yarın geçer).
    tr = timezone(timedelta(hours=TR_OFFSET_HOURS))
    end_of_day_local = datetime.combine(td, time(23, 59, 59, 999_999), tzinfo=tr)
    cutoff_utc = end_of_day_local.astimezone(timezone.utc)

    cards = (
        db.query(ReviewCard)
        .options(joinedload(ReviewCard.topic).joinedload(Topic.subject))
        .join(Topic, Topic.id == ReviewCard.topic_id)
        .filter(
            ReviewCard.student_id == student_id,
            Topic.subject_id == subject_id,
            ReviewCard.review_count > 0,         # hiç çalışılmamış değil
            ReviewCard.due_at.isnot(None),
            ReviewCard.due_at <= cutoff_utc,     # bugün için vadesi geldi
        )
        .all()
    )

    items: list[dict] = []
    for c in cards:
        if not c.topic:
            continue
        score, reasons = _struggle_score(c)
        if score < 10.0:
            continue
        items.append({
            "topic_id": c.topic_id,
            "topic_name": c.topic.name,
            "score": round(score),
            "reasons": reasons,
            "state": c.state,
            "lapse_count": c.lapse_count or 0,
            "card_id": c.id,
        })
    items.sort(key=lambda x: -x["score"])
    items = items[:8]

    return templates.TemplateResponse(
        "teacher/partials/review_struggle_chips.html",
        {"request": request, "items": items, "target_date": td, "subject_id": subject_id},
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
