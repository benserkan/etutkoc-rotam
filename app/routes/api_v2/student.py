"""API v2 — Öğrenci paneli endpoint'leri (Dalga 2 Paket 1 + 2).

Paket 1 (salt okunur):
  GET  /api/v2/student/day?date=YYYY-MM-DD       → StudentDayResponse
  GET  /api/v2/student/week?start=YYYY-MM-DD     → StudentWeekResponse
  GET  /api/v2/student/books                     → StudentBooksResponse
  GET  /api/v2/student/book-grid?book_id=N       → BookGridResponse
  GET  /api/v2/student/badges                    → PendingBadgesResponse

Paket 2 (mutations — OOB swap karşılığı):
  POST /api/v2/student/tasks/{task_id}/complete          → MutationResponse[StudentTask]
  POST /api/v2/student/tasks/{task_id}/uncomplete        → MutationResponse[StudentTask]
  POST /api/v2/student/tasks/{task_id}/items/{item_id}/set-completed
                                                          → MutationResponse[StudentTask]

Service çağrıları MEVCUT olanların aynısı — task_service.complete_task,
uncomplete_task, set_item_completion, event_triggers.on_task_completed,
gamification.evaluate_badges_for_student.

Jinja `app/routes/student.py` DOKUNULMAZ; Caddyfile aktivasyon Paket 7 sonu.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    Book,
    BookSection,
    GoalKind,
    GoalStatus,
    PomodoroSession,
    RequestStatus,
    ReviewCard,
    StudentBook,
    StudentGoal,
    Subject,
    Task,
    TaskBookItem,
    TaskRequest,
    TaskStatus,
    Topic,
    User,
    UserRole,
)
from app.models.focus import PomodoroKind
from app.routes.api_v2.dependencies import get_current_user_v2, _auth_error
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.student import (
    DOW_KEYS,
    AddRequestBody,
    WeekPrintDay,
    WeekPrintResponse,
    WeekPrintTask,
    BookCell,
    BookGridResponse,
    BookSectionGrid,
    BookSectionOption,
    BookSectionsResponse,
    BurnoutSignal as ApiBurnoutSignal,
    CanRequestMatrix,
    ChangeRequestBody,
    DaySummary,
    DnaResponse,
    DnaSubjectActivity,
    DnaTrend,
    FocusEndBody,
    FocusResponse,
    FocusSession,
    FocusStartBody,
    FocusTodaySummary,
    GoalCreateBody,
    GoalItem,
    GoalListResponse,
    GoalProgressBody,
    GoalSummary,
    GoalToggleBody,
    PendingBadgesResponse,
    ProjectionPanel,
    QuestionRequestBody,
    RemoveRequestBody,
    ReplaceRequestBody,
    ResourceBook,
    ResourceSidebar,
    ResourceSubjectGroup,
    ReviewBreakdown,
    ReviewCardItem,
    ReviewRateBody,
    ReviewResponse,
    CompleteTaskBody,
    SetCompletedBody,
    StudentBooksResponse,
    StudentDayResponse,
    StudentRequestItem,
    StudentRequestListResponse,
    StudentTask,
    StudentTaskItem,
    StudentWeekDay,
    StudentWeekResponse,
)
from app.services.analytics import student_snapshot
from app.services.request_service import (
    RequestError,
    create_add_request,
    create_change_request,
    create_question,
    create_remove_request,
    create_replace_request,
    pending_count_for_student,
    withdraw_request as svc_withdraw_request,
)
from app.services.task_service import (
    ReservationError,
    complete_task as svc_complete_task,
    set_item_completion as svc_set_item_completion,
    uncomplete_task as svc_uncomplete_task,
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/student", tags=["v2-student"])


# Türkçe gün etiketleri (Pzt=0..Paz=6 — Python isoweekday-1)
_DOW_LABELS_TR = (
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"
)


# ============================================================================
# Auth helper — öğrenci-only kapı
# ============================================================================


def _require_student(user: User = Depends(get_current_user_v2)) -> User:
    """Sadece STUDENT rolüne izin ver."""
    if user.role != UserRole.STUDENT:
        raise _auth_error(
            "Bu uç nokta öğrenci hesabı bekler",
            "role_required",
            http_status=403,
        )
    return user


# ============================================================================
# Builder yardımcıları — DB veri → Pydantic
# ============================================================================


def _build_task_item(item: TaskBookItem) -> StudentTaskItem:
    section = item.section
    topic_name = section.topic.name if (section and section.topic) else None
    section_label = section.label if section else None

    # max_completable: kalemin planlı sayısını şimdilik tavan say.
    # Daha fazlasını yapmak için CHANGE talebi → öğretmen onayı (mevcut akış).
    # Frontend yine de server'ın 422 over_capacity uyarısıyla geri toplanır.
    return StudentTaskItem(
        id=item.id,
        book_id=item.book_id,
        book_name=item.book.name if item.book else (item.label or "Deneme"),
        section_id=item.book_section_id,
        section_label=section_label,
        topic_name=topic_name,
        planned=item.planned_count,
        completed=item.completed_count,
        is_full=(item.completed_count >= item.planned_count and item.planned_count > 0),
        max_completable=item.planned_count,
        correct=item.correct_count,
        wrong=item.wrong_count,
    )


def _validate_result_distribution(
    *,
    completed: int,
    correct: int | None,
    wrong: int | None,
    is_book_item: bool,
) -> None:
    """D/Y validation — birim duyarlı.

    Kitaplı görev (`is_book_item=True`):
      - completed = **test sayısı** (rezerv-bağlı, ≤ planned)
      - correct/wrong = **soru sayısı** (her test çoklu soru içerir; örn. 3 test = 30 soru)
      - Kural: sadece c ≥ 0, w ≥ 0. Toplam üst sınır YOK (bağımsız metric).

    Kitapsız deneme (`is_book_item=False`):
      - completed = **soru sayısı** (planned = soru)
      - correct/wrong = **soru sayısı** (aynı birim)
      - Kural: c ≥ 0, w ≥ 0 ve c + w ≤ completed (boş = completed − c − w)
    """
    c = correct if correct is not None else 0
    w = wrong if wrong is not None else 0
    if c < 0 or w < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation_error",
                "code": "invalid_result_distribution",
                "message": "Doğru ve yanlış sayıları negatif olamaz.",
            },
        )
    # Toplam ≤ completed kuralı yalnız kitapsız denemede geçerli (aynı birim).
    if not is_book_item and c + w > completed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation_error",
                "code": "invalid_result_distribution",
                "message": (
                    f"Doğru ({c}) + Yanlış ({w}) = {c + w}, çözdüğün "
                    f"({completed}) sorudan fazla olamaz."
                ),
            },
        )


def _has_pending_request_for_task(db: Session, task_id: int, student_id: int) -> bool:
    return (
        db.query(TaskRequest)
        .filter(
            TaskRequest.task_id == task_id,
            TaskRequest.student_id == student_id,
            TaskRequest.status == RequestStatus.PENDING,
        )
        .first()
        is not None
    )


def _build_task(db: Session, task: Task, today: date) -> StudentTask:
    items = [_build_task_item(it) for it in task.book_items]
    planned = sum(it.planned for it in items)
    completed = sum(it.completed for it in items)
    pct = (completed / planned) if planned > 0 else 0.0
    # scheduled_hour DB'de int (saat); StudentTask için "HH:MM" string'e dönüştür.
    sched_hour_str: str | None = None
    if task.scheduled_hour is not None:
        try:
            sched_hour_str = f"{int(task.scheduled_hour):02d}:00"
        except (TypeError, ValueError):
            sched_hour_str = None
    return StudentTask(
        id=task.id,
        title=task.title or "",
        type=task.type.value if task.type else "test",
        status=task.status.value if task.status else "pending",
        date=task.date.isoformat(),
        scheduled_hour=sched_hour_str,
        period=task.period,
        items=items,
        planned_count=planned,
        completed_count=completed,
        pct=pct,
        is_future_blocked=(task.date > today),
        is_past=(task.date < today),
        has_pending_request=_has_pending_request_for_task(db, task.id, task.student_id),
    )


def _build_resource_sidebar(db: Session, student_id: int) -> ResourceSidebar:
    """Sticky XL sidebar verisi — ders × kitap × rezerv/tamam/kalan."""
    assignments = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student_id)
        .all()
    )

    subjects_map: dict[int, ResourceSubjectGroup] = {}
    total_t = total_r = total_c = total_rem = 0

    for sb in assignments:
        book = sb.book
        if not book or not book.subject:
            continue
        rb = ResourceBook(
            student_book_id=sb.id,
            book_id=book.id,
            book_name=book.name,
            book_type=book.type.value,
            total_tests=sb.total_tests,
            reserved_tests=sb.reserved_tests,
            completed_tests=sb.completed_tests,
            remaining_tests=sb.remaining_tests,
        )
        sid = book.subject.id
        if sid not in subjects_map:
            subjects_map[sid] = ResourceSubjectGroup(
                subject_id=sid,
                subject_name=book.subject.name,
                total_tests=0, reserved_tests=0,
                completed_tests=0, remaining_tests=0,
                books=[],
            )
        grp = subjects_map[sid]
        grp.books.append(rb)
        grp.total_tests += rb.total_tests
        grp.reserved_tests += rb.reserved_tests
        grp.completed_tests += rb.completed_tests
        grp.remaining_tests += rb.remaining_tests
        total_t += rb.total_tests
        total_r += rb.reserved_tests
        total_c += rb.completed_tests
        total_rem += rb.remaining_tests

    # subject_order: subject.order varsa o, yoksa isim
    subject_list = sorted(
        subjects_map.values(),
        key=lambda g: (g.subject_name.lower(),),
    )
    # Her grup içinde kitaplar isme göre
    for g in subject_list:
        g.books.sort(key=lambda b: b.book_name.lower())

    return ResourceSidebar(
        total_tests=total_t,
        reserved_tests=total_r,
        completed_tests=total_c,
        remaining_tests=total_rem,
        subjects=subject_list,
    )


def _build_projection_panel(snapshot) -> ProjectionPanel | None:
    """StudentSnapshot.projection → ProjectionPanel (Pydantic)."""
    p = snapshot.projection if snapshot else None
    if p is None:
        return None

    # DOW dict'lerini int-key'den string-key'e çevir
    def _normalize_dow(d: dict, with_measure: bool = False) -> dict:
        out: dict = {}
        for idx, key in enumerate(DOW_KEYS):
            v = d.get(idx) if d else None
            if with_measure:
                out[key] = bool(v)
            else:
                # 0.0..1.0 — ölçülemedi ise None
                if v is None:
                    out[key] = None
                else:
                    out[key] = float(v)
        return out

    measured = _normalize_dow(p.dow_hit_measured, with_measure=True)
    rates: dict[str, float | None] = {}
    for idx, key in enumerate(DOW_KEYS):
        if not measured[key]:
            rates[key] = None
            continue
        v = p.dow_hit_rates.get(idx) if p.dow_hit_rates else None
        rates[key] = float(v) if v is not None else None

    return ProjectionPanel(
        exam_date=p.exam_date.isoformat() if p.exam_date else None,
        days_left=p.days_left,
        effective_days=p.effective_days,
        buffer_days=p.buffer_days,
        methodology=p.methodology,
        confidence_level=p.confidence_level,
        rate_per_day=float(p.rate_per_day),
        projected_completable=int(p.projected_completable),
        gap=int(p.gap),
        required_rate=float(p.required_rate),
        dow_hit_rates=rates,
        dow_hit_measured=measured,
    )


def _build_day_summary(tasks: list[Task]) -> DaySummary:
    total_items = sum(len(t.book_items) for t in tasks)
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)
    pct = (completed / planned) if planned > 0 else 0.0
    return DaySummary(
        total_tasks=len(tasks),
        total_items=total_items,
        planned_count=planned,
        completed_count=completed,
        pct=pct,
    )


def _load_day_tasks(db: Session, student_id: int, d: date) -> list[Task]:
    """Eşdeğer: app/routes/student.py:_load_day_tasks (Jinja). Aynı sorgu."""
    return (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(
            Task.student_id == student_id,
            Task.date == d,
            Task.is_draft.is_(False),
        )
        .order_by(Task.scheduled_hour.is_(None), Task.scheduled_hour, Task.order, Task.id)
        .all()
    )


def _build_can_request_matrix(d: date, today: date) -> CanRequestMatrix:
    """Gelecek/geçmiş/bugün'e göre öğrencinin yapabileceği talepler."""
    is_future = d > today
    is_past = d < today
    # Talepler yalnız mevcut/gelecekteki günler için anlamlı.
    # Geçmiş günde de soru sorulabilir (mevcut akışta var) ama add/remove sınırlı.
    return CanRequestMatrix(
        change=not is_past,
        replace=not is_past,
        remove=not is_past,
        question=True,            # her zaman serbest
        add=is_future or d == today,
    )


# ============================================================================
# Endpoint'ler
# ============================================================================


@router.get("/day", response_model=StudentDayResponse)
def student_day_v2(
    date_param: str | None = Query(None, alias="date"),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Belirli bir günün görev listesi + özet + sidebar + projeksiyon.

    Eşdeğer Jinja: app/routes/student.py:140 (student_day).
    """
    today = date.today()
    try:
        d = date.fromisoformat(date_param) if date_param else today
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation",
                "code": "invalid_date",
                "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
            },
        )

    tasks = _load_day_tasks(db, user.id, d)
    snapshot = student_snapshot(db, user, today=today)

    return StudentDayResponse(
        date=d.isoformat(),
        is_today=(d == today),
        is_future=(d > today),
        is_past=(d < today),
        prev_date=(d - timedelta(days=1)).isoformat(),
        next_date=(d + timedelta(days=1)).isoformat(),
        tasks=[_build_task(db, t, today) for t in tasks],
        summary=_build_day_summary(tasks),
        sidebar=_build_resource_sidebar(db, user.id),
        projection=_build_projection_panel(snapshot),
        can_request=_build_can_request_matrix(d, today),
    )


@router.get("/week", response_model=StudentWeekResponse)
def student_week_v2(
    start_param: str | None = Query(None, alias="start"),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """7 günlük plan görünümü (salt-okunur).

    Eşdeğer Jinja: app/routes/student.py:229 (student_week).
    Pzt-Pazar değil, istenen günden başlayan 7 günlük pencere.
    """
    today = date.today()
    try:
        start = date.fromisoformat(start_param) if start_param else None
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation",
                "code": "invalid_date",
                "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
            },
        )

    # WP4 — Öğrenci sayfası açılınca aktif program varsa onun başlangıcına snap.
    # Yoksa bugün — eski davranış (geri uyum).
    if start is None:
        from app.services.weekly_program_service import get_active_program
        active_prog = get_active_program(
            db, student_id=user.id, today=today,
        )
        start = active_prog.start_date if active_prog else today

    days = [start + timedelta(days=i) for i in range(7)]
    end = days[-1]

    tasks_all = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(
            Task.student_id == user.id,
            Task.date.in_(days),
            Task.is_draft.is_(False),
        )
        .order_by(Task.date, Task.scheduled_hour.is_(None), Task.scheduled_hour, Task.order, Task.id)
        .all()
    )
    tasks_by_day: dict[date, list[Task]] = {d: [] for d in days}
    for t in tasks_all:
        tasks_by_day[t.date].append(t)

    week_days: list[StudentWeekDay] = []
    total_planned = 0
    total_completed = 0
    for d in days:
        day_tasks = tasks_by_day[d]
        planned = sum(it.planned_count for t in day_tasks for it in t.book_items)
        completed = sum(it.completed_count for t in day_tasks for it in t.book_items)
        pct = (completed / planned) if planned > 0 else 0.0
        dow_idx = d.weekday()  # Mon=0..Sun=6
        week_days.append(StudentWeekDay(
            date=d.isoformat(),
            dow_label=_DOW_LABELS_TR[dow_idx],
            is_today=(d == today),
            is_future=(d > today),
            is_past=(d < today),
            tasks_count=len(day_tasks),
            planned=planned,
            completed=completed,
            pct=pct,
            tasks=[_build_task(db, t, today) for t in day_tasks],
        ))
        total_planned += planned
        total_completed += completed

    total_pct = (total_completed / total_planned) if total_planned > 0 else 0.0

    return StudentWeekResponse(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        prev_start=(start - timedelta(days=7)).isoformat(),
        next_start=(start + timedelta(days=7)).isoformat(),
        days=week_days,
        total_planned=total_planned,
        total_completed=total_completed,
        total_pct=total_pct,
    )


# ----------------------- Week print payload -----------------------
_TR_WEEKDAYS_LONG = (
    "Pazartesi", "Salı", "Çarşamba", "Perşembe",
    "Cuma", "Cumartesi", "Pazar",
)
_TR_MONTHS = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)


@router.get("/week-print", response_model=WeekPrintResponse)
def student_week_print_v2(
    start_param: str | None = Query(None, alias="start"),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """A4 yatay yazdırma için 7 günlük plan + geçmiş tutturma + hafta notları.

    Mevcut Jinja `/student/week/print` ile aynı veri payload'ı — sadece JSON
    biçiminde. Next.js print sayfası bu endpoint'i tüketir.

    Geçmiş tutturma: her gün için son 12 aynı haftagünündeki planlı/tamamlanan
    oranı (history_pct). Bu metrik, gelecek hafta görsel ipuçları için kritik.
    """
    today = date.today()
    try:
        start = date.fromisoformat(start_param) if start_param else today
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation",
                "code": "invalid_date",
                "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
            },
        )

    days = [start + timedelta(days=i) for i in range(7)]
    end_date = days[-1]

    # Aktif görevler — eager yüklü
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(
            Task.student_id == user.id,
            Task.date.in_(days),
            Task.is_draft.is_(False),
        )
        .order_by(Task.date, Task.order, Task.id)
        .all()
    )
    tasks_by_day: dict[date, list[Task]] = {d: [] for d in days}
    for t in tasks:
        tasks_by_day[t.date].append(t)

    # Geçmiş 12 aynı haftagünü için tutturma
    PAST_WEEKS = 12
    past_dates_by_day: dict[date, list[date]] = {
        d: [d - timedelta(days=7 * i) for i in range(1, PAST_WEEKS + 1)] for d in days
    }
    all_past_dates: list[date] = []
    for lst in past_dates_by_day.values():
        all_past_dates.extend(lst)
    past_rows: list[tuple[date, int, int]] = []
    if all_past_dates:
        rows = (
            db.query(Task.date, TaskBookItem.planned_count, TaskBookItem.completed_count)
            .join(TaskBookItem, TaskBookItem.task_id == Task.id)
            .filter(
                Task.student_id == user.id,
                Task.date.in_(all_past_dates),
                Task.is_draft.is_(False),
            )
            .all()
        )
        past_rows = [(r[0], r[1] or 0, r[2] or 0) for r in rows]

    # Akademik yıl + sınav etiketi
    academic_year_name: str | None = None
    if user.academic_year_id:
        from app.models import AcademicYear
        ay = db.query(AcademicYear).filter(AcademicYear.id == user.academic_year_id).first()
        academic_year_name = ay.name if ay else None
    exam_date_iso: str | None = None
    exam_label: str | None = None
    try:
        if user.effective_exam_date:
            exam_date_iso = user.effective_exam_date.isoformat()
            exam_label = user.effective_exam_label
    except Exception:
        # User modelinin property'leri bazen academic_year ile birlikte güvenli erişilemez
        pass

    # Hafta notları (önce tam denk gelen, yoksa anchor block)
    from app.models import WeekNote
    from app.routes.teacher_program import _student_week_start

    note_week_start = start
    notes_q = (
        db.query(WeekNote)
        .filter(WeekNote.student_id == user.id, WeekNote.week_start == note_week_start)
        .order_by(WeekNote.order.asc(), WeekNote.id.asc())
        .all()
    )
    if not notes_q:
        anchor_start = _student_week_start(db, user, start)
        if anchor_start != start:
            notes_q = (
                db.query(WeekNote)
                .filter(WeekNote.student_id == user.id, WeekNote.week_start == anchor_start)
                .order_by(WeekNote.order.asc(), WeekNote.id.asc())
                .all()
            )
    week_notes = [n.body for n in notes_q if (n.body or "").strip()]

    # Günlere yansıt
    print_days: list[WeekPrintDay] = []
    for d in days:
        # history hesabı
        pset = set(past_dates_by_day[d])
        planned_sum = 0
        completed_sum = 0
        for dt, pc, cc in past_rows:
            if dt in pset:
                planned_sum += pc
                completed_sum += cc
        history_pct: int | None = (
            round(100 * completed_sum / planned_sum) if planned_sum > 0 else None
        )

        # task satırları
        day_tasks: list[WeekPrintTask] = []
        for t in tasks_by_day[d]:
            items = t.book_items
            if len(items) == 1:
                it = items[0]
                day_tasks.append(WeekPrintTask(
                    title=t.title or "",
                    is_single_item=True,
                    book_name=it.book.name if it.book else None,
                    section_label=it.section.label if it.section else None,
                    topic_name=it.section.topic.name if (it.section and it.section.topic) else None,
                    planned_count=it.planned_count,
                ))
            elif items:
                total = sum((bi.planned_count or 0) for bi in items)
                day_tasks.append(WeekPrintTask(
                    title=t.title or "",
                    is_single_item=False,
                    planned_count=total,
                ))
            else:
                # Kalemsiz görev — TaskTypeLiteral etiketi göstermeye yararlı
                day_tasks.append(WeekPrintTask(
                    title=t.title or "",
                    is_single_item=False,
                    planned_count=0,
                    type_label=t.type.value if t.type else None,
                ))

        print_days.append(WeekPrintDay(
            date=d.isoformat(),
            day_of_month=d.day,
            month_index=d.month - 1,
            dow_index=d.weekday(),
            dow_label=_TR_WEEKDAYS_LONG[d.weekday()],
            month_label=_TR_MONTHS[d.month - 1],
            task_count=len(tasks_by_day[d]),
            history_pct=history_pct,
            history_samples=planned_sum,
            tasks=day_tasks,
        ))

    return WeekPrintResponse(
        student_name=user.full_name,
        grade_level=user.grade_level,
        academic_year_name=academic_year_name,
        exam_label=exam_label,
        exam_date=exam_date_iso,
        start_date=start.isoformat(),
        end_date=end_date.isoformat(),
        start_day=start.day,
        start_month_label=_TR_MONTHS[start.month - 1],
        start_dow_label=_TR_WEEKDAYS_LONG[start.weekday()],
        end_day=end_date.day,
        end_month_label=_TR_MONTHS[end_date.month - 1],
        end_year=end_date.year,
        days=print_days,
        week_notes=week_notes,
    )


@router.get("/books", response_model=StudentBooksResponse)
def student_books_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrenciye atanmış tüm kitaplar (ders × kitap grupları).

    Eşdeğer Jinja: app/routes/student.py:631 (student_books).
    """
    sidebar = _build_resource_sidebar(db, user.id)
    return StudentBooksResponse(
        total_tests=sidebar.total_tests,
        reserved_tests=sidebar.reserved_tests,
        completed_tests=sidebar.completed_tests,
        remaining_tests=sidebar.remaining_tests,
        subjects=sidebar.subjects,
    )


@router.get("/book-grid", response_model=BookGridResponse)
def student_book_grid_v2(
    book_id: int = Query(...),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Sinema-koltuk grid — kitap içi test bazında yeşil/sarı/gri kareler.

    Eşdeğer Jinja: app/routes/student.py:414 (student_book_grid).
    """
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
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "book_not_assigned",
                "message": "Bu kitap size atanmamış.",
            },
        )

    # Mevcut helper'ı reuse et (öğretmen/öğrenci aynı slot mantığı)
    from app.routes.teacher_program import build_book_grid_slots

    pmap = {p.book_section_id: p for p in sb.section_progress}
    section_ids = [sec.id for sec in sb.book.sections]
    slots_map = build_book_grid_slots(db, user.id, section_ids, teacher_student_id=None)

    sections_data: list[BookSectionGrid] = []
    total_done = 0
    total_res = 0
    for sec in sb.book.sections:
        sp = pmap.get(sec.id)
        completed = sp.completed_count if sp else 0
        reserved = sp.reserved_count if sp else 0
        slots = slots_map.get(sec.id, {"completed": [], "reserved": []})
        done_slots = slots.get("completed", [])
        res_slots = slots.get("reserved", [])

        cells: list[BookCell] = []
        # 1..test_count arası numaralandır; ilk N tanesi tamamlanmış, sonraki M
        # tanesi rezerve, kalan boş (UI'da renkli — bu sıra Jinja şablonuyla aynı).
        idx = 0
        for s in done_slots:
            idx += 1
            cells.append(BookCell(
                number=idx,
                state="DONE",
                task_id=s.get("task_id"),
                task_date=s.get("date"),
            ))
        for s in res_slots:
            idx += 1
            cells.append(BookCell(
                number=idx,
                state="RESERVED",
                task_id=s.get("task_id"),
                task_date=s.get("date"),
            ))
        while idx < sec.test_count:
            idx += 1
            cells.append(BookCell(number=idx, state="FREE"))

        sections_data.append(BookSectionGrid(
            section_id=sec.id,
            label=sec.label,
            topic_name=sec.topic.name if sec.topic else None,
            test_count=sec.test_count,
            completed=completed,
            reserved=reserved,
            cells=cells,
        ))
        total_done += completed
        total_res += reserved

    return BookGridResponse(
        student_book_id=sb.id,
        book_id=sb.book.id,
        book_name=sb.book.name,
        subject_name=sb.book.subject.name if sb.book.subject else "—",
        book_type=sb.book.type.value,
        total_tests=sb.book.total_tests,
        total_completed=total_done,
        total_reserved=total_res,
        sections=sections_data,
    )


@router.get("/book-sections", response_model=BookSectionsResponse)
def student_book_sections_v2(
    book_id: int = Query(..., gt=0),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
) -> BookSectionsResponse:
    """Kaynak değiştir / Yeni görev iste modali için cascade.

    Eşdeğer Jinja: `app/routes/student.py:465` (student_cascade_sections,
    HTMX HTML fragment dönüyordu).

    Şartlar:
      - Kitap öğrenciye atanmış olmalı (aksi 404)
      - `BookSection.book_id` filtre ile yalnız o kitabın bölümleri
      - `remaining = test_count - reserved - completed` (kalan kapasite)
    """
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
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "book_not_assigned",
                "message": "Bu kitap size atanmamış.",
            },
        )
    pmap = {p.book_section_id: p for p in sb.section_progress}
    items: list[BookSectionOption] = []
    for sec in sb.book.sections:
        sp = pmap.get(sec.id)
        reserved = sp.reserved_count if sp else 0
        completed = sp.completed_count if sp else 0
        remaining = max(0, sec.test_count - reserved - completed)
        items.append(BookSectionOption(
            id=sec.id,
            label=sec.label,
            topic_name=sec.topic.name if sec.topic else None,
            remaining=remaining,
            total=sec.test_count,
        ))
    is_deneme = sb.book.type.value in ("brans_denemesi", "genel_deneme")
    return BookSectionsResponse(
        book_id=book_id,
        is_deneme=is_deneme,
        items=items,
    )


@router.get("/badges", response_model=PendingBadgesResponse)
def student_badges_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """60 saniyelik polling endpoint'i — öğretmen yanıtı bekleyen talep sayısı.

    Eşdeğer Jinja: app/routes/partials.py:48 (student_pending_count, HTMX).
    """
    from app.services.request_service import pending_count_for_student
    from app.models.task import Task, TaskBookItem
    count = pending_count_for_student(db, user.id)
    # 'Bugün' rozeti: bugünün YAYINLANMIŞ + tamamlanmamış görev sayısı (tikleyince düşer)
    today_open = (
        db.query(TaskBookItem.task_id)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(
            Task.student_id == user.id,
            Task.date == date.today(),
            Task.is_draft.is_(False),
            TaskBookItem.completed_count < TaskBookItem.planned_count,
        )
        .distinct()
        .count()
    )
    return PendingBadgesResponse(
        pending_count=count,
        today_open_count=today_open,
        checked_at=datetime.now(timezone.utc),
    )


# ============================================================================
# Paket 2 — Task mutations (OOB swap karşılığı)
# ============================================================================


def _get_own_task(db: Session, task_id: int, student_id: int) -> Task:
    """Görevi yükle ve sahiplik kontrol et. 404 — başkasının görevi de 404.

    Eşdeğer Jinja: app/routes/student.py:656 (_get_own_task).
    """
    task = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.id == task_id, Task.student_id == student_id)
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "task_not_found",
                "message": "Görev bulunamadı.",
            },
        )
    return task


def _ensure_not_future(task: Task) -> None:
    """Gelecek tarihli görevin tamamlama tıklamasını engelle.

    Eşdeğer Jinja: app/routes/student.py:671 (_ensure_not_future).
    """
    if task.date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation",
                "code": "future_task_blocked",
                "message": (
                    f"Bu görev {task.date.strftime('%d.%m.%Y')} tarihli — "
                    "gelecek bir günü tıklayamazsın. O gün gelince tikleyebilirsin."
                ),
            },
        )


def _reservation_error_response(e: ReservationError) -> HTTPException:
    """ReservationError → 422 RESERVE_OVER_CAPACITY (kullanıcı kararı: 400 değil 422).

    Frontend form/validasyon hatası olarak yakalayabilsin.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "validation",
            "code": "RESERVE_OVER_CAPACITY",
            "message": str(e),
        },
    )


def _fire_task_completed_event_safe(db: Session, student: User) -> None:
    """Görev COMPLETED'a yeni geçtiğinde event'i fırlat — hata endpoint'i bozmasın.

    Kullanıcı kuralı (Paket 2 onayı): gamification/oyunlaştırma hatası, öğrencinin
    görevini tamamlamasına ASLA engel olmamalı. Her try/except endpoint sonucunu
    asla 5xx'e çevirmez; sadece logger'a yazar.

    Eşdeğer Jinja: app/routes/student.py:39 (_fire_task_completed_event).
    """
    # 1) Veli bildirim olayı
    try:
        from app.services.event_triggers import on_task_completed
        on_task_completed(db, student)
    except Exception as e:
        logger.exception("on_task_completed (v2) hata student=%s: %s", student.id, e)

    # 2) Otonom resume (auto-pause edilmişse görev sonrası uyandır)
    try:
        from app.models import AuditAction
        from app.services.audit import log_action
        from app.services.pause import maybe_auto_resume
        if maybe_auto_resume(db, student):
            log_action(
                db,
                action=AuditAction.USER_AUTO_RESUME,
                actor_id=None,
                target_type="user",
                target_id=student.id,
                details={"trigger": "task_completed", "channel": "api_v2"},
            )
    except Exception as e:
        logger.exception("auto_resume (v2) hata student=%s: %s", student.id, e)


def _evaluate_badges_safe(db: Session, student_id: int) -> None:
    """Rozet değerlendirmesi — hata sonucu bozmasın."""
    try:
        from app.services.gamification import evaluate_badges_for_student
        evaluate_badges_for_student(db, student_id=student_id)
    except Exception as e:
        logger.exception("badge eval (v2) hata student=%s: %s", student_id, e)


def _invalidate_keys_for_task(task: Task, user: User) -> list[str]:
    """MutationResponse.invalidate listesi — frontend TanStack Query key prefix'leri.

    Sözleşme (kullanıcının kırmızı çizgisi R-006/R-007 için kritik):
      - student:{user_id}:day:{date_iso}        → o günün view'ı
      - student:{user_id}:sidebar               → sticky XL Kaynak Durumu
      - student:{user_id}:summary:{date_iso}    → gün özeti şeridi
      - badges:student:{user_id}:pending        → talep sayısı rozet
    """
    date_iso = task.date.isoformat()
    return [
        f"student:{user.id}:day:{date_iso}",
        f"student:{user.id}:sidebar",
        f"student:{user.id}:summary:{date_iso}",
        f"badges:student:{user.id}:pending",
    ]


@router.post(
    "/tasks/{task_id}/complete",
    response_model=MutationResponse[StudentTask],
)
def complete_task_v2(
    task_id: int,
    body: CompleteTaskBody | None = None,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Görevi tamamla — idempotent (zaten COMPLETED ise event tetiklenmez, 200 döner).

    Opsiyonel D/Y (body.correct / body.wrong): yalnız **tek kalemli** görevde
    uygulanır. Çoklu kalemli görevde yok sayılır.

    Eşdeğer Jinja: app/routes/student.py:683 (complete_task).
    """
    task = _get_own_task(db, task_id, user.id)
    _ensure_not_future(task)

    was_completed = task.status == TaskStatus.COMPLETED

    # D/Y validation — tek kalemli görevde uygulanır (servis de tek-kalem kontrolü yapar)
    correct = body.correct if body else None
    wrong = body.wrong if body else None
    if len(task.book_items) == 1:
        single = task.book_items[0]
        _validate_result_distribution(
            completed=single.planned_count,  # complete → planlanan tam
            correct=correct,
            wrong=wrong,
            is_book_item=single.book_id is not None,
        )

    try:
        svc_complete_task(db, task, correct=correct, wrong=wrong)
    except ReservationError as e:
        db.rollback()
        raise _reservation_error_response(e)

    if not was_completed:
        # Yalnız yeni COMPLETED'a geçişte event + badge — idempotent davranış için kritik
        _fire_task_completed_event_safe(db, user)
        _evaluate_badges_safe(db, user.id)

    db.commit()
    db.refresh(task)

    return MutationResponse[StudentTask](
        data=_build_task(db, task, date.today()),
        invalidate=_invalidate_keys_for_task(task, user),
    )


@router.post(
    "/tasks/{task_id}/uncomplete",
    response_model=MutationResponse[StudentTask],
)
def uncomplete_task_v2(
    task_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Tamamlamayı geri al — gelecek bloğu uygulanmaz (yanlış tikleri düzeltme izni).

    Eşdeğer Jinja: app/routes/student.py:704 (uncomplete_task).
    """
    task = _get_own_task(db, task_id, user.id)
    # uncomplete'ta _ensure_not_future ÇAĞRILMAZ — mevcut Jinja akışıyla aynı
    try:
        svc_uncomplete_task(db, task)
    except ReservationError as e:
        # Pratikte uncomplete kapasiteyi aşmaz ama defansif yakalama
        db.rollback()
        raise _reservation_error_response(e)
    db.commit()
    db.refresh(task)

    return MutationResponse[StudentTask](
        data=_build_task(db, task, date.today()),
        invalidate=_invalidate_keys_for_task(task, user),
    )


@router.post(
    "/tasks/{task_id}/items/{item_id}/set-completed",
    response_model=MutationResponse[StudentTask],
)
def set_item_completed_v2(
    task_id: int,
    item_id: int,
    body: SetCompletedBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Tek kalemin tamamlanan sayısını manuel ayarla (kısmi tamamlama).

    Eşdeğer Jinja: app/routes/student.py:719 (set_item_completed).

    Görev status'ü item toplamına göre yeniden hesaplanır:
      total_done == 0           → PENDING
      total_done >= total_planned → COMPLETED (event + badge)
      else                       → PARTIAL
    """
    task = _get_own_task(db, task_id, user.id)
    _ensure_not_future(task)

    item = next((i for i in task.book_items if i.id == item_id), None)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "item_not_found",
                "message": "Görev kalemi bulunamadı.",
            },
        )

    # D/Y validation — body.completed üst sınır; servis klampleyince tutarsızlık
    # önlemek için klamplenmiş completed üzerinden kontrol.
    effective_completed = max(0, min(body.completed, item.planned_count))
    _validate_result_distribution(
        completed=effective_completed,
        correct=body.correct,
        wrong=body.wrong,
        is_book_item=item.book_id is not None,
    )

    try:
        svc_set_item_completion(
            db, item, body.completed, correct=body.correct, wrong=body.wrong
        )
    except ReservationError as e:
        db.rollback()
        raise _reservation_error_response(e)

    # Görev status'ünü yeniden değerlendir (eşdeğer Jinja:739-760)
    total_planned = sum(i.planned_count for i in task.book_items)
    total_done = sum(i.completed_count for i in task.book_items)

    previously_completed = task.status == TaskStatus.COMPLETED
    new_completed = False

    if total_done == 0:
        task.status = TaskStatus.PENDING
        task.completed_at = None
    elif total_done >= total_planned:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        new_completed = not previously_completed
    else:
        task.status = TaskStatus.PARTIAL
        task.completed_at = None

    if new_completed:
        _fire_task_completed_event_safe(db, user)
        _evaluate_badges_safe(db, user.id)

    db.commit()
    db.refresh(task)

    return MutationResponse[StudentTask](
        data=_build_task(db, task, date.today()),
        invalidate=_invalidate_keys_for_task(task, user),
    )


# ============================================================================
# Paket 3 — Student Requests (talep sistemi)
# ============================================================================


def _request_error_response(e: RequestError) -> HTTPException:
    """RequestError → 422 RESERVE_OVER_CAPACITY veya 400 request_error.

    Service mesajları kullanıcı-dostu Türkçe; doğrudan iletilir.
    """
    msg = str(e)
    # Kapasite ile ilgili mesajları 422 RESERVE_OVER_CAPACITY altında topla
    # (frontend form validasyonu için 400 ile 422 ayrımı kullanıcı kararı).
    if "kapasite" in msg.lower() or "kalan" in msg.lower() or "sınır" in msg.lower():
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "RESERVE_OVER_CAPACITY",
                "message": msg,
            },
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": "validation",
            "code": "request_error",
            "message": msg,
        },
    )


def _ensure_no_pending_request(db: Session, task_id: int, student_id: int) -> None:
    """Aynı görev üzerinde zaten PENDING bir change/replace/remove varsa 409."""
    existing = (
        db.query(TaskRequest)
        .filter(
            TaskRequest.task_id == task_id,
            TaskRequest.student_id == student_id,
            TaskRequest.status == RequestStatus.PENDING,
            TaskRequest.type.in_(["change", "replace", "remove"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "request_already_pending",
                "message": "Bu görev için zaten bekleyen bir talep var.",
            },
        )


def _ensure_task_not_completed(task: Task) -> None:
    """Tamamlanmış görev üzerinde change/replace/remove yapılmaz → 422."""
    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "task_already_completed",
                "message": "Bu görev zaten tamamlandı; üzerinde talep oluşturulamaz.",
            },
        )


def _build_request_item(req: TaskRequest) -> StudentRequestItem:
    """TaskRequest → StudentRequestItem (Pydantic)."""
    return StudentRequestItem(
        id=req.id,
        type=req.type.value,
        status=req.status.value,
        task_id=req.task_id,
        # REMOVE onaylanınca task silindi + FK SET NULL: snapshot'tan göster
        task_title=(req.task.title if req.task else req.task_title_snapshot),
        task_date=(
            req.task.date.isoformat() if req.task
            else (req.task_date_snapshot.isoformat() if req.task_date_snapshot else None)
        ),
        message=req.message,
        proposed_book_id=req.proposed_book_id,
        proposed_book_name=req.proposed_book.name if req.proposed_book else None,
        proposed_section_id=req.proposed_section_id,
        proposed_section_label=req.proposed_section.label if req.proposed_section else None,
        proposed_count=req.proposed_count,
        proposed_date=req.proposed_date.isoformat() if req.proposed_date else None,
        teacher_response=req.teacher_response,
        created_at=req.created_at,
        responded_at=req.responded_at,
    )


def _invalidate_keys_for_request(
    user: User,
    task_date: date | None = None,
) -> list[str]:
    """MutationResponse.invalidate — talep mutasyonları için.

    Talep açıldığında/silindiğinde:
      - student:{id}:requests           → talep listesi sayfası
      - badges:student:{id}:pending     → öğrenci & öğretmen rozet polling
      - student:{id}:day:{date}         → görev kartında "bekleyen talep" rozeti
      - student:{id}:summary:{date}     → günün özeti (gerekirse)
    """
    keys = [
        f"student:{user.id}:requests",
        f"badges:student:{user.id}:pending",
    ]
    if task_date:
        keys.append(f"student:{user.id}:day:{task_date.isoformat()}")
        keys.append(f"student:{user.id}:summary:{task_date.isoformat()}")
    return keys


@router.post(
    "/tasks/{task_id}/requests/change",
    response_model=MutationResponse[StudentRequestItem],
)
def request_change_v2(
    task_id: int,
    body: ChangeRequestBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Sayı değiştir talebi — proposed_count zorunlu."""
    task = _get_own_task(db, task_id, user.id)
    _ensure_task_not_completed(task)
    _ensure_no_pending_request(db, task_id, user.id)
    try:
        req = create_change_request(
            db, student=user, task=task,
            proposed_count=body.proposed_count, message=body.message,
        )
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_response(e)
    db.refresh(req)
    return MutationResponse[StudentRequestItem](
        data=_build_request_item(req),
        invalidate=_invalidate_keys_for_request(user, task.date),
    )


@router.post(
    "/tasks/{task_id}/requests/replace",
    response_model=MutationResponse[StudentRequestItem],
)
def request_replace_v2(
    task_id: int,
    body: ReplaceRequestBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Kaynak değiştir talebi — kitap/bölüm/sayı zorunlu."""
    task = _get_own_task(db, task_id, user.id)
    _ensure_task_not_completed(task)
    _ensure_no_pending_request(db, task_id, user.id)
    try:
        req = create_replace_request(
            db, student=user, task=task,
            new_book_id=body.new_book_id,
            new_section_id=body.new_section_id,
            new_count=body.new_count,
            message=body.message,
        )
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_response(e)
    db.refresh(req)
    return MutationResponse[StudentRequestItem](
        data=_build_request_item(req),
        invalidate=_invalidate_keys_for_request(user, task.date),
    )


@router.post(
    "/tasks/{task_id}/requests/remove",
    response_model=MutationResponse[StudentRequestItem],
)
def request_remove_v2(
    task_id: int,
    body: RemoveRequestBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Görev çıkar talebi."""
    task = _get_own_task(db, task_id, user.id)
    _ensure_task_not_completed(task)
    _ensure_no_pending_request(db, task_id, user.id)
    try:
        req = create_remove_request(
            db, student=user, task=task, message=body.message,
        )
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_response(e)
    db.refresh(req)
    return MutationResponse[StudentRequestItem](
        data=_build_request_item(req),
        invalidate=_invalidate_keys_for_request(user, task.date),
    )


@router.post(
    "/tasks/{task_id}/requests/question",
    response_model=MutationResponse[StudentRequestItem],
)
def request_question_v2(
    task_id: int,
    body: QuestionRequestBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Görevle ilgili soru sor — tamamlanmış görevde de açık, çoklu PENDING serbest."""
    task = _get_own_task(db, task_id, user.id)
    try:
        req = create_question(
            db, student=user, task=task, message=body.message,
        )
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_response(e)
    db.refresh(req)
    return MutationResponse[StudentRequestItem](
        data=_build_request_item(req),
        invalidate=_invalidate_keys_for_request(user, task.date),
    )


@router.post(
    "/days/{day_iso}/requests/add",
    response_model=MutationResponse[StudentRequestItem],
)
def request_add_v2(
    day_iso: str,
    body: AddRequestBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Yeni görev önerisi — geçmiş gün engellenir."""
    try:
        target = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_date",
                "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
            },
        )
    if target < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation",
                "code": "past_day_blocked",
                "message": "Geçmiş bir güne yeni görev eklenemez.",
            },
        )
    try:
        req = create_add_request(
            db, student=user, target_date=target,
            book_id=body.book_id, section_id=body.section_id,
            proposed_count=body.proposed_count, message=body.message,
        )
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_response(e)
    db.refresh(req)
    return MutationResponse[StudentRequestItem](
        data=_build_request_item(req),
        invalidate=_invalidate_keys_for_request(user, target),
    )


@router.post(
    "/requests/{request_id}/withdraw",
    response_model=MutationResponse[StudentRequestItem],
)
def request_withdraw_v2(
    request_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Bekleyen talebi geri çek — yalnız sahip + PENDING."""
    req = (
        db.query(TaskRequest)
        .options(
            joinedload(TaskRequest.task),
            joinedload(TaskRequest.proposed_book),
            joinedload(TaskRequest.proposed_section),
        )
        .filter(TaskRequest.id == request_id, TaskRequest.student_id == user.id)
        .first()
    )
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "request_not_found",
                "message": "Talep bulunamadı.",
            },
        )
    try:
        svc_withdraw_request(db, student=user, req=req)
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_response(e)
    db.refresh(req)
    task_date = req.task.date if req.task else req.proposed_date
    return MutationResponse[StudentRequestItem](
        data=_build_request_item(req),
        invalidate=_invalidate_keys_for_request(user, task_date),
    )


@router.get("/requests", response_model=StudentRequestListResponse)
def list_requests_v2(
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrencinin tüm taleplerini listele (en yeni önce, en fazla 100).

    status filtresi: pending | answered | all (default: all).
    'answered' = approved + rejected + resolved + withdrawn (yani non-pending).
    """
    q = (
        db.query(TaskRequest)
        .options(
            joinedload(TaskRequest.task),
            joinedload(TaskRequest.proposed_book),
            joinedload(TaskRequest.proposed_section),
        )
        .filter(TaskRequest.student_id == user.id)
    )
    if status_filter == "pending":
        q = q.filter(TaskRequest.status == RequestStatus.PENDING)
    elif status_filter == "answered":
        q = q.filter(TaskRequest.status != RequestStatus.PENDING)
    # 'all' veya tanımsız → filtre yok

    rows = q.order_by(TaskRequest.created_at.desc()).limit(100).all()
    items = [_build_request_item(r) for r in rows]
    pending = pending_count_for_student(db, user.id)
    return StudentRequestListResponse(
        items=items,
        total=len(items),
        pending_count=pending,
    )


# ============================================================================
# Paket 4 — Secondary features (focus / dna / review / goals)
# ============================================================================


# -------------------- Focus (Pomodoro) --------------------


_POMODORO_KIND_MAP = {
    PomodoroKind.WORK: "work",
    PomodoroKind.SHORT_BREAK: "short_break",
    PomodoroKind.LONG_BREAK: "long_break",
}


def _build_focus_session(s: PomodoroSession, now: datetime) -> FocusSession:
    """PomodoroSession → FocusSession Pydantic (server elapsed hesaplı)."""
    started = s.started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    is_active = s.ended_at is None
    elapsed = 0
    if is_active and started is not None:
        elapsed = int(max(0, (now - started).total_seconds()))
    return FocusSession(
        id=s.id,
        kind=_POMODORO_KIND_MAP.get(s.kind, "work"),
        started_at=s.started_at,
        ended_at=s.ended_at,
        planned_minutes=s.planned_minutes,
        actual_minutes=s.actual_minutes,
        interrupted=bool(s.interrupted),
        label=s.label,
        is_active=is_active,
        elapsed_seconds=elapsed,
    )


def _today_iso() -> str:
    return date.today().isoformat()


def _focus_invalidate_keys(user: User) -> list[str]:
    """Focus mutasyonları — günün KPI'sı + sidebar etkilenmez (sadece focus + summary)."""
    return [
        f"student:{user.id}:focus",
        f"student:{user.id}:summary:{_today_iso()}",
    ]


@router.get("/focus", response_model=FocusResponse)
def student_focus_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Pomodoro paneli — aktif seans + bugün özeti + son seanslar + streak + puan.

    Eşdeğer Jinja: app/routes/focus.py:48 (student_focus).
    auto_close_stale_sessions (3 saat üzeri açık seansları otomatik kapat)
    yan etkisi korunur — UI yenilenince temizlenmiş veri görünür.
    """
    from app.services.gamification import compute_points, compute_streak
    from app.services.pomodoro import (
        auto_close_stale_sessions,
        recent_sessions as svc_recent_sessions,
        today_summary as svc_today_summary,
    )

    now = datetime.now(timezone.utc)
    closed = auto_close_stale_sessions(db, student_id=user.id, hours=3, now=now)
    if closed:
        db.commit()

    active = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.student_id == user.id,
            PomodoroSession.ended_at.is_(None),
        )
        .order_by(PomodoroSession.started_at.desc())
        .first()
    )
    summary_dc = svc_today_summary(db, student_id=user.id, now=now)
    recent = svc_recent_sessions(db, student_id=user.id, limit=10)
    streak = compute_streak(db, student_id=user.id, now=now)
    points_bd = compute_points(db, student_id=user.id)
    points_total = points_bd.total if hasattr(points_bd, "total") else int(points_bd)

    return FocusResponse(
        active_session=_build_focus_session(active, now) if active else None,
        today=FocusTodaySummary(
            work_sessions=summary_dc.work_sessions,
            work_minutes=summary_dc.work_minutes,
            break_minutes=summary_dc.break_minutes,
            total_minutes=summary_dc.total_minutes,
            interrupted_count=summary_dc.interrupted_count,
        ),
        recent_sessions=[_build_focus_session(s, now) for s in recent],
        streak_days=streak,
        points=points_total,
    )


@router.post(
    "/focus/start",
    response_model=MutationResponse[FocusSession],
)
def student_focus_start_v2(
    body: FocusStartBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Yeni pomodoro seansı başlat. Açık seans varsa 409 focus_session_already_open."""
    from app.services.pomodoro import start_session as svc_start_session

    # Açık seans var mı?
    existing_active = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.student_id == user.id,
            PomodoroSession.ended_at.is_(None),
        )
        .first()
    )
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "focus_session_already_open",
                "message": "Zaten açık bir pomodoro seansın var; önce onu bitir.",
            },
        )

    try:
        pk = PomodoroKind(body.kind)
    except ValueError:
        pk = PomodoroKind.WORK
    now = datetime.now(timezone.utc)
    sess = svc_start_session(
        db,
        student_id=user.id,
        planned_minutes=body.planned_minutes,
        kind=pk,
        label=body.label,
        now=now,
    )
    db.commit()
    db.refresh(sess)
    return MutationResponse[FocusSession](
        data=_build_focus_session(sess, now),
        invalidate=_focus_invalidate_keys(user),
    )


def _get_own_session(db: Session, session_id: int, student_id: int) -> PomodoroSession:
    sess = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.id == session_id,
            PomodoroSession.student_id == student_id,
        )
        .first()
    )
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "focus_session_not_found",
                "message": "Pomodoro seansı bulunamadı.",
            },
        )
    return sess


@router.post(
    "/focus/{session_id}/stop",
    response_model=MutationResponse[FocusSession],
)
def student_focus_stop_v2(
    session_id: int,
    body: FocusEndBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Pomodoro seansını normal bitir + rozet kontrolü.

    Zaten kapalı seans → 400 focus_session_already_closed.
    """
    from app.services.pomodoro import end_session as svc_end_session

    sess = _get_own_session(db, session_id, user.id)
    if sess.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation",
                "code": "focus_session_already_closed",
                "message": "Bu seans zaten kapalı.",
            },
        )
    now = datetime.now(timezone.utc)
    svc_end_session(
        db,
        session=sess,
        actual_minutes=body.actual_minutes,
        interrupted=body.interrupted,
        now=now,
    )
    _evaluate_badges_safe(db, user.id)
    db.commit()
    db.refresh(sess)
    return MutationResponse[FocusSession](
        data=_build_focus_session(sess, now),
        invalidate=_focus_invalidate_keys(user),
    )


@router.post(
    "/focus/{session_id}/cancel",
    response_model=MutationResponse[FocusSession],
)
def student_focus_cancel_v2(
    session_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Pomodoro seansını yarıda terk et — actual=elapsed, interrupted=True.

    Zaten kapalı seans → 400 focus_session_already_closed.
    """
    from app.services.pomodoro import end_session as svc_end_session

    sess = _get_own_session(db, session_id, user.id)
    if sess.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation",
                "code": "focus_session_already_closed",
                "message": "Bu seans zaten kapalı.",
            },
        )
    now = datetime.now(timezone.utc)
    svc_end_session(
        db,
        session=sess,
        actual_minutes=None,           # server elapsed'i kullansın
        interrupted=True,
        now=now,
    )
    db.commit()
    db.refresh(sess)
    return MutationResponse[FocusSession](
        data=_build_focus_session(sess, now),
        invalidate=_focus_invalidate_keys(user),
    )


# -------------------- DNA (Çalışma profili + burnout) --------------------


@router.get("/dna", response_model=DnaResponse)
def student_dna_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Çalışma DNA profili + burnout sinyalleri (read-only).

    Eşdeğer Jinja: app/routes/dna.py:56 (student_dna).
    """
    from app.services.burnout import compute_burnout
    from app.services.study_dna import DAY_NAMES_TR, compute_profile

    now = datetime.now(timezone.utc)
    profile = compute_profile(db, student_id=user.id, now=now)
    burnout = compute_burnout(db, student_id=user.id, now=now)

    by_subject = [
        DnaSubjectActivity(
            subject_id=sa.subject_id,
            subject_name=sa.subject_name,
            planned=sa.planned,
            completed=sa.completed,
            completion_rate=float(sa.completion_rate),
        )
        for sa in profile.by_subject
    ]
    trend = None
    if profile.trend is not None:
        trend = DnaTrend(
            direction=profile.trend.direction,
            this_week_completed=profile.trend.this_week_completed,
            last_week_completed=profile.trend.last_week_completed,
            delta_pct=profile.trend.delta_pct,
        )
    signals = [
        ApiBurnoutSignal(
            kind=s.kind,
            severity=s.severity,
            label=s.label,
            emoji=s.emoji,
            detail=s.detail,
            metric=s.metric,
        )
        for s in burnout.signals
    ]
    peak_day_name = None
    if profile.peak_day_idx is not None and 0 <= profile.peak_day_idx < 7:
        peak_day_name = DAY_NAMES_TR[profile.peak_day_idx]

    return DnaResponse(
        window_days=profile.window_days,
        has_enough_data=profile.has_enough_data,
        total_completed=profile.total_completed,
        total_planned=profile.total_planned,
        completion_rate=float(profile.completion_rate),
        chronotype=profile.chronotype,
        peak_hour=profile.peak_hour,
        peak_day_idx=profile.peak_day_idx,
        peak_day_name=peak_day_name,
        heatmap=profile.heatmap,
        morning_count=profile.morning_count,
        afternoon_count=profile.afternoon_count,
        evening_count=profile.evening_count,
        night_count=profile.night_count,
        weekend_count=profile.weekend_count,
        weekday_count=profile.weekday_count,
        by_subject=by_subject,
        trend=trend,
        hour_data_confidence=profile.hour_data_confidence,
        burnout_risk_score=burnout.risk_score,
        burnout_risk_level=burnout.risk_level,
        burnout_signals=signals,
    )


# -------------------- Review (FSRS spaced repetition) --------------------


def _build_review_card(card: ReviewCard) -> ReviewCardItem:
    topic_name = card.topic.name if card.topic else "—"
    subject_name = (
        card.topic.subject.name if (card.topic and card.topic.subject) else None
    )
    return ReviewCardItem(
        id=card.id,
        topic_id=card.topic_id,
        topic_name=topic_name,
        subject_name=subject_name,
        state=card.state,
        due_at=card.due_at,
        last_reviewed_at=card.last_reviewed_at,
        last_rating=card.last_rating,
        stability=float(card.stability),
        difficulty=float(card.difficulty),
        review_count=card.review_count,
        lapse_count=card.lapse_count,
    )


@router.get("/review", response_model=ReviewResponse)
def student_review_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Vadesi gelmiş tekrar kartları + state breakdown.

    Eşdeğer Jinja: app/routes/review.py:56 (student_review_index).
    """
    from app.services.review_scheduler import cards_breakdown, get_due_cards

    now = datetime.now(timezone.utc)
    due = get_due_cards(db, student_id=user.id, now=now, limit=100)
    bd = cards_breakdown(db, student_id=user.id, now=now)
    return ReviewResponse(
        due_cards=[_build_review_card(c) for c in due],
        breakdown=ReviewBreakdown(
            new=bd.new, learning=bd.learning, review=bd.review,
            relearning=bd.relearning, due_now=bd.due_now, total=bd.total,
        ),
    )


@router.post(
    "/review/{card_id}/rate",
    response_model=MutationResponse[ReviewCardItem],
)
def student_review_rate_v2(
    card_id: int,
    body: ReviewRateBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Karta rating ver (1-4) → FSRS state güncelle + rozet kontrolü.

    rating ∉ {1,2,3,4} → 422 invalid_rating. Başkasının kartı → 404.
    """
    from app.services.fsrs import VALID_RATINGS
    from app.services.review_scheduler import get_card, record_review

    if body.rating not in VALID_RATINGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_rating",
                "message": "Geçersiz rating; 1-4 aralığı bekleniyor.",
            },
        )
    card = get_card(db, card_id=card_id, student_id=user.id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "review_card_not_found",
                "message": "Tekrar kartı bulunamadı.",
            },
        )
    now = datetime.now(timezone.utc)
    record_review(db, card=card, rating=body.rating, now=now)
    _evaluate_badges_safe(db, user.id)
    db.commit()
    db.refresh(card)
    return MutationResponse[ReviewCardItem](
        data=_build_review_card(card),
        invalidate=[
            f"student:{user.id}:review",
            f"student:{user.id}:badges",
        ],
    )


# -------------------- Goals (Kişisel hedefler) --------------------


def _build_goal(g: StudentGoal) -> GoalItem:
    return GoalItem(
        id=g.id,
        parent_id=g.parent_id,
        kind=g.kind.value,
        status=g.status.value,
        title=g.title,
        description=g.description,
        target_value=g.target_value,
        current_value=g.current_value,
        unit=g.unit,
        target_date=g.target_date.isoformat() if g.target_date else None,
        is_auto_generated=bool(g.is_auto_generated),
        progress_pct=g.progress_pct,
        achieved_at=g.achieved_at,
        created_at=g.created_at,
    )


def _goal_invalidate_keys(user: User) -> list[str]:
    return [f"student:{user.id}:goals"]


def _personal_kind_filter() -> list[GoalKind]:
    """Öğrenci panelinde gösterilecek kişisel hedef tipleri.

    EXAM_TARGET ve auto-generated SUBJECT'ler Jinja akışında gizlendiği için
    burada da aynı şekilde dışlıyoruz.
    """
    return [
        GoalKind.WEEKLY, GoalKind.DAILY, GoalKind.CUSTOM,
        GoalKind.TOPIC,  # öğretmenin TOPIC seed'i dahil, manuel görüntü ister
        GoalKind.SUBJECT,  # is_auto_generated=False olanlar dahil
    ]


@router.get("/goals", response_model=GoalListResponse)
def student_goals_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrencinin kişisel hedefleri + özet.

    Eşdeğer Jinja: app/routes/goals.py:102 (student_goals_page).
    EXAM_TARGET auto + SUBJECT auto kayıtları gizler (kişisel hedeflere odaklı).
    """
    from app.services.goals import student_goal_summary

    rows = (
        db.query(StudentGoal)
        .filter(
            StudentGoal.student_id == user.id,
            StudentGoal.status != GoalStatus.ABANDONED,
        )
        .order_by(StudentGoal.created_at.asc())
        .all()
    )
    # Gizleme kuralı: auto-generated EXAM_TARGET ve auto-generated SUBJECT
    visible = [
        g for g in rows
        if not (g.is_auto_generated and g.kind in (GoalKind.EXAM_TARGET, GoalKind.SUBJECT))
    ]
    summary_dict = student_goal_summary(db, student_id=user.id)
    # Servis next_target_date'i zaten "YYYY-MM-DD" string olarak veriyor; tekrar
    # dönüştürme yapma (docstring yanıltıcı — geri uyumluluk için olduğu gibi
    # bırakıyoruz, Jinja sayfaları da bu davranışa bağlı).
    raw_next = summary_dict.get("next_target_date")
    next_target_date_iso = (
        raw_next if isinstance(raw_next, str)
        else raw_next.isoformat() if raw_next is not None
        else None
    )
    summary = GoalSummary(
        total=summary_dict.get("total", 0),
        active=summary_dict.get("active", 0),
        achieved=summary_dict.get("achieved", 0),
        abandoned=summary_dict.get("abandoned", 0),
        overall_pct=summary_dict.get("overall_pct"),
        next_target_date=next_target_date_iso,
    )
    return GoalListResponse(
        items=[_build_goal(g) for g in visible],
        summary=summary,
    )


@router.post(
    "/goals",
    response_model=MutationResponse[GoalItem],
)
def student_goals_create_v2(
    body: GoalCreateBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Yeni kişisel hedef oluştur (kind ∈ weekly/daily/custom/topic).

    title boşsa 422 invalid_title. target_date geçersiz format → 422 invalid_date.
    """
    from app.services.goals import create_goal

    title_clean = (body.title or "").strip()
    if not title_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_title",
                "message": "Başlık boş olamaz.",
            },
        )
    target_date_parsed: date | None = None
    if body.target_date:
        try:
            target_date_parsed = date.fromisoformat(body.target_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "invalid_date",
                    "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
                },
            )
    try:
        kind_enum = GoalKind(body.kind)
    except ValueError:
        kind_enum = GoalKind.CUSTOM

    g = create_goal(
        db, student=user, kind=kind_enum, title=title_clean,
        description=body.description,
        target_value=body.target_value,
        current_value=body.current_value,
        unit=(body.unit or "").strip() or None,
        target_date=target_date_parsed,
        created_by_user_id=user.id,
        autocommit=False,
    )
    db.commit()
    db.refresh(g)
    return MutationResponse[GoalItem](
        data=_build_goal(g),
        invalidate=_goal_invalidate_keys(user),
    )


def _get_own_goal(db: Session, goal_id: int, student_id: int) -> StudentGoal:
    g = db.get(StudentGoal, goal_id)
    if g is None or g.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "goal_not_found",
                "message": "Hedef bulunamadı.",
            },
        )
    return g


@router.post(
    "/goals/{goal_id}/progress",
    response_model=MutationResponse[GoalItem],
)
def student_goals_progress_v2(
    goal_id: int,
    body: GoalProgressBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Yaprak hedefin current_value'sini güncelle.

    Auto-generated hedefe yazma → 403 goal_read_only.
    """
    from app.services.goals import update_goal

    g = _get_own_goal(db, goal_id, user.id)
    if g.is_auto_generated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "code": "goal_read_only",
                "message": "Otomatik üretilmiş hedefler elle güncellenemez.",
            },
        )
    update_goal(db, goal=g, current_value=body.current_value, autocommit=False)
    db.commit()
    db.refresh(g)
    return MutationResponse[GoalItem](
        data=_build_goal(g),
        invalidate=_goal_invalidate_keys(user),
    )


@router.post(
    "/goals/{goal_id}/toggle",
    response_model=MutationResponse[GoalItem],
)
def student_goals_toggle_v2(
    goal_id: int,
    body: GoalToggleBody,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Hedefi ACHIEVED ↔ ACTIVE arası al.

    achieved=True  → ACHIEVED + achieved_at=now
    achieved=False → ACTIVE  + achieved_at=None (rollback)
    """
    from app.services.goals import mark_achieved

    g = _get_own_goal(db, goal_id, user.id)
    if body.achieved:
        mark_achieved(db, goal=g, autocommit=False)
    else:
        # Rollback: status=ACTIVE + achieved_at=None
        g.status = GoalStatus.ACTIVE
        g.achieved_at = None
        db.flush()
    db.commit()
    db.refresh(g)
    return MutationResponse[GoalItem](
        data=_build_goal(g),
        invalidate=_goal_invalidate_keys(user),
    )
