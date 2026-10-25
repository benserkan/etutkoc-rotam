"""Deneme görevleri — koçun "Deneme" formu (D1, 2026-10-20).

  GET  /teacher/students/{id}/deneme-options  → dersler (standart soru), öğrencinin deneme
                                                kitapları (sıradaki denemeler), genel deneme
                                                türleri, koçun sık kullandığı kalıplar
  POST /teacher/students/{id}/deneme-tasks     → 1 görev, N deneme kalemi (1 kalem = 1 deneme)

Kural ve hesaplar tek merkezde: app.services.deneme_service.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Book, BookSection, StudentBook, Subject, User
from app.routes.api_v2.dependencies import assert_active_coaching
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.teacher import TaskCreateBody, TaskItemBody, TeacherTask
from app.routes.api_v2.teacher import (
    _build_teacher_task,
    _create_task_with_items,
    _get_owned_student,
    _invalidate_for_task,
    _require_teacher,
    _reservation_to_http,
)
from app.services import deneme_service as ds
from app.services.task_service import ReservationError

router = APIRouter(prefix="/teacher", tags=["v2-deneme-tasks"])


# ---------------------------------------------------------------------------
# Şemalar
# ---------------------------------------------------------------------------


class DenemeSubjectOut(BaseModel):
    id: int
    name: str
    exam_section: str | None = None
    standard_question_count: int | None = None
    deneme_book_count: int = 0


class DenemeSectionOut(BaseModel):
    section_id: int
    label: str
    remaining: int


class DenemeBookOut(BaseModel):
    book_id: int
    name: str
    type: str                       # brans_denemesi | genel_deneme
    subject_id: int
    question_count: int | None = None
    question_source: str            # label | book | standard | none
    remaining_total: int
    next_sections: list[DenemeSectionOut]


class DenemePresetOut(BaseModel):
    key: str
    label: str
    exam_section: str
    question_count: int


class DenemeTemplateOut(BaseModel):
    kind: str
    label: str
    count: int
    question_count: int
    subject_id: int | None = None
    exam_section: str | None = None
    book_id: int | None = None
    uses: int
    group_key: str | None = None


class DenemeBransGroupOut(BaseModel):
    key: str
    label: str
    exam_section: str
    question_count: int
    covers: str


class DenemeOptionsResponse(BaseModel):
    subjects: list[DenemeSubjectOut]
    brans_groups: list[DenemeBransGroupOut] = []
    books: list[DenemeBookOut]
    genel_presets: list[DenemePresetOut]
    templates: list[DenemeTemplateOut]
    max_count: int = ds.MAX_DENEME_PER_TASK


class DenemeTaskBody(BaseModel):
    date: str
    period: str | None = None
    scheduled_hour: int | None = None
    is_draft: bool | None = None
    kind: Literal["brans", "genel"]
    count: int = Field(1, ge=1, le=ds.MAX_DENEME_PER_TASK)
    question_count: int | None = Field(None, ge=1, le=ds.MAX_QUESTIONS)
    subject_id: int | None = None   # branş (kitapsız) — kitaplıda kitaptan
    book_id: int | None = None      # kaynaklı deneme
    genel_key: str | None = None    # genel deneme türü (GENEL_PRESETS anahtarı)
    group_key: str | None = None    # birleşik branş (BRANS_GROUPS anahtarı: tyt_fen …)
    name: str | None = Field(None, max_length=120)  # isteğe bağlı ad ("Özdebir TG-4")
    notes: str | None = None


class DenemePendingRow(BaseModel):
    task_id: int
    item_id: int
    date: str
    task_title: str
    label: str
    exam_kind: str
    question_count: int | None = None
    days_waiting: int
    exam_section: str | None = None
    duration_minutes: int | None = None


class DenemePendingResponse(BaseModel):
    count: int
    tasks: int
    rows: list[DenemePendingRow]


def build_pending_response(db, student_id: int) -> DenemePendingResponse:
    rows = ds.pending_result_rows(db, student_id)
    return DenemePendingResponse(count=len(rows), tasks=len({r["task_id"] for r in rows}),
                                 rows=[DenemePendingRow(**r) for r in rows])


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _err(code: str, message: str, http: int = status.HTTP_422_UNPROCESSABLE_ENTITY) -> HTTPException:
    return HTTPException(status_code=http, detail={"error": "validation", "code": code, "message": message})


def _student_subjects(db: Session, student: User, coach_id: int) -> list[Subject]:
    """Görev kutusu + müfredat sekmesiyle aynı ders kümesi + kitabı olan dersler."""
    from app.services.curriculum_progress import _applicable_subjects

    subjects = list(_applicable_subjects(db, student, coach_id))
    seen_ids = {s.id for s in subjects}
    seen_names = {s.name for s in subjects}
    for b in (
        db.query(Book)
        .join(StudentBook, StudentBook.book_id == Book.id)
        .filter(StudentBook.student_id == student.id, StudentBook.archived_at.is_(None))
        .all()
    ):
        subj = b.subject
        if subj is not None and subj.id not in seen_ids and subj.name not in seen_names:
            subjects.append(subj)
            seen_ids.add(subj.id)
            seen_names.add(subj.name)
    subjects.sort(key=lambda s: (s.order or 0, s.name or ""))
    return subjects


def _assigned_deneme_book(db: Session, student: User, book_id: int) -> Book:
    book = (
        db.query(Book)
        .join(StudentBook, StudentBook.book_id == Book.id)
        .filter(
            Book.id == book_id,
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),
        )
        .first()
    )
    if book is None:
        raise _err("book_not_found", "Bu deneme kitabı öğrenciye atanmış değil.", status.HTTP_404_NOT_FOUND)
    if book.type not in ds.DENEME_BOOK_TYPES:
        raise _err("not_deneme_book", "Seçilen kaynak bir deneme kitabı değil.")
    return book


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


@router.get("/students/{student_id}/deneme-options", response_model=DenemeOptionsResponse)
def deneme_options(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> DenemeOptionsResponse:
    student = _get_owned_student(db, student_id, user.id)
    subjects = _student_subjects(db, student, user.id)
    books = ds.deneme_books_for_student(db, student)
    book_count: dict[int, int] = {}
    for b in books:
        book_count[b.subject_id] = book_count.get(b.subject_id, 0) + 1
    known = {s.id for s in subjects}
    # Deneme kitabının dersi müfredat kümesinde yoksa yine de listelenir.
    for b in books:
        if b.subject_id not in known:
            s = db.get(Subject, b.subject_id)
            if s is not None:
                subjects.append(s)
                known.add(s.id)
    templates = ds.coach_templates(
        db, coach_id=user.id, student=student,
        subject_ids={s.id for s in subjects}, book_ids={b.book_id for b in books},
    )
    return DenemeOptionsResponse(
        subjects=[
            DenemeSubjectOut(
                id=s.id, name=s.name, exam_section=ds.exam_section_for_subject(s),
                standard_question_count=ds.standard_question_count(s),
                deneme_book_count=book_count.get(s.id, 0),
            )
            for s in subjects
        ],
        books=[
            DenemeBookOut(
                book_id=b.book_id, name=b.name, type=b.type, subject_id=b.subject_id,
                question_count=b.question_count, question_source=b.question_source,
                remaining_total=b.remaining_total,
                next_sections=[DenemeSectionOut(section_id=x.section_id, label=x.label,
                                                remaining=x.remaining) for x in b.next_sections],
            )
            for b in books
        ],
        genel_presets=[
            DenemePresetOut(key=p.key, label=p.label, exam_section=p.exam_section,
                            question_count=p.question_count)
            for p in ds.genel_presets_for(student)
        ],
        templates=[DenemeTemplateOut(**t.__dict__) for t in templates],
        brans_groups=[DenemeBransGroupOut(**g.__dict__) for g in ds.brans_groups_for(student)],
    )


@router.post("/students/{student_id}/deneme-tasks", response_model=MutationResponse[TeacherTask])
def create_deneme_task(
    student_id: int,
    body: DenemeTaskBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    n = body.count
    items: list[TaskItemBody] = []
    warnings: list[str] = []
    name = (body.name or "").strip() or None

    if body.book_id is not None:
        book = _assigned_deneme_book(db, student, body.book_id)
        picked = ds.pick_sections(db, student, book, n)
        if not picked:
            raise _err("book_has_no_sections", "Bu deneme kitabının bölümü yok — önce denemeleri ekleyin.")
        first_sec: BookSection = picked[0][0]
        qn = body.question_count
        if qn is None:
            qn, _src = ds.resolve_question_count(book=book, section=first_sec, subject=book.subject)
        if qn is None:
            raise _err("question_count_required", "Deneme başına soru sayısını girin.")
        # Koçun girdiği sayı kitapta kayıtlı değilse kitaba yazılır (bir dahaki sefere sorulmaz).
        if (body.question_count and not book.avg_questions_per_test
                and ds.question_count_from_label(first_sec.label) is None):
            book.avg_questions_per_test = body.question_count
        kind = ds.EXAM_KIND_BRANS if book.type == ds.DENEME_BOOK_TYPES[0] else ds.EXAM_KIND_GENEL
        section = ds.exam_section_for_subject(book.subject)
        if kind == ds.EXAM_KIND_GENEL and body.genel_key:
            preset = next((p for p in ds.genel_presets_for(student) if p.key == body.genel_key), None)
            if preset is not None:
                section = preset.exam_section
        over = sum(1 for _, o in picked if o)
        if over:
            warnings.append(
                f"Kitapta yalnız {n - over} deneme boştu; {over} deneme kayıtlı sayının üstünde atandı."
            )
        for sec, o in picked:
            items.append(TaskItemBody(
                book_id=book.id, section_id=sec.id, planned_count=1, allow_over_capacity=o,
                exam_kind=kind, exam_section=section, question_count=qn,
            ))
        title = ds.compose_title(
            kind=kind, count=n, question_count=qn, subject=book.subject, book=book,
            section_labels=[s.label for s, _ in picked], custom_name=name,
        )
        task_type = "test"
    elif body.kind == ds.EXAM_KIND_BRANS and body.group_key:
        grp = next((g for g in ds.brans_groups_for(student) if g.key == body.group_key), None)
        if grp is None:
            raise _err("group_not_found", "Bu birleşik branş denemesi bu öğrenci için uygun değil.")
        qn = body.question_count or grp.question_count
        title = ds.compose_title(kind=ds.EXAM_KIND_BRANS, count=n, question_count=qn,
                                 custom_name=name or f"{grp.label} branş denemesi")
        for i in range(n):
            items.append(TaskItemBody(
                book_id=None, section_id=None, planned_count=1,
                label=(f"{grp.label} {i + 1}/{n}" if n > 1 else grp.label),
                exam_kind=ds.EXAM_KIND_BRANS, exam_section=grp.exam_section,
                subject_id=None, question_count=qn,
            ))
        task_type = "other"
    elif body.kind == ds.EXAM_KIND_BRANS:
        if body.subject_id is None:
            raise _err("subject_required", "Branş denemesi için ders seçin.")
        allowed = {s.id: s for s in _student_subjects(db, student, user.id)}
        subj = allowed.get(body.subject_id)
        if subj is None:
            raise _err("subject_not_found", "Seçilen ders bu öğrencinin dersleri arasında değil.")
        qn = body.question_count or ds.standard_question_count(subj)
        if qn is None:
            raise _err("question_count_required", "Deneme başına soru sayısını girin.")
        section = ds.exam_section_for_subject(subj)
        title = ds.compose_title(kind=ds.EXAM_KIND_BRANS, count=n, question_count=qn,
                                 subject=subj, custom_name=name)
        for i in range(n):
            items.append(TaskItemBody(
                book_id=None, section_id=None, planned_count=1,
                label=(f"Deneme {i + 1}/{n}" if n > 1 else "Deneme"),
                exam_kind=ds.EXAM_KIND_BRANS, exam_section=section,
                subject_id=subj.id, question_count=qn,
            ))
        task_type = "other"
    else:
        preset = next((p for p in ds.genel_presets_for(student) if p.key == body.genel_key), None)
        if preset is None:
            all_presets = [p for grp in ds.GENEL_PRESETS.values() for p in grp]
            raw = next((p for p in all_presets if p[0] == body.genel_key), None)
            if raw is None:
                raise _err("genel_key_required", "Genel deneme türünü seçin.")
            preset = ds.GenelPreset(key=raw[0], label=raw[1], exam_section=raw[2], question_count=raw[3])
        qn = body.question_count or preset.question_count
        title = ds.compose_title(kind=ds.EXAM_KIND_GENEL, count=n, question_count=qn,
                                 genel_label=preset.label, custom_name=name)
        for i in range(n):
            items.append(TaskItemBody(
                book_id=None, section_id=None, planned_count=1,
                label=(f"{preset.label} {i + 1}/{n}" if n > 1 else preset.label),
                exam_kind=ds.EXAM_KIND_GENEL, exam_section=preset.exam_section,
                question_count=qn,
            ))
        task_type = "other"

    payload = TaskCreateBody(
        date=body.date, type=task_type, title=title,
        scheduled_hour=body.scheduled_hour, period=body.period,
        is_draft=body.is_draft, notes=body.notes, items=items,
    )
    try:
        task = _create_task_with_items(db, student=student, payload=payload)
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# HAVUZ (D1b): aynı deneme formu havuza kalem ekler (quantity = deneme adedi).
# Kaba alınınca her deneme ayrı görev satırı olur (pool_mode.put_in_cup).
# ---------------------------------------------------------------------------


class PoolDenemeBody(BaseModel):
    kind: Literal["brans", "genel"]
    count: int = Field(1, ge=1, le=ds.MAX_DENEME_PER_TASK)
    question_count: int | None = Field(None, ge=1, le=ds.MAX_QUESTIONS)
    subject_id: int | None = None
    book_id: int | None = None
    genel_key: str | None = None
    name: str | None = Field(None, max_length=120)
    day_hint: str | None = None
    teacher_homework: bool = False


class DenemeAnalysisPoint(BaseModel):
    exam_id: int
    date: str
    title: str
    net: float
    questions: int | None = None
    net_pct: float | None = None
    correct: int
    wrong: int
    blank: int
    duration_minutes: int | None = None


class DenemeAnalysisSeries(BaseModel):
    key: str
    label: str
    kind: Literal["genel", "brans"]
    subject: str | None = None
    section: str
    count: int
    correct: int
    wrong: int
    blank: int
    accuracy_pct: float | None = None
    blank_rate_pct: float | None = None
    avg_net_pct: float | None = None
    last_net_pct: float | None = None
    min_per_question: float | None = None
    timed_count: int = 0
    normal_low: float | None = None
    normal_high: float | None = None
    last_position: Literal["below", "within", "above"] | None = None
    decline_run: int = 0
    slope: float | None = None
    direction: Literal["up", "down", "flat"] | None = None
    projected_net_pct: float | None = None
    pending: int = 0
    test_accuracy_pct: float | None = None
    test_answered: int | None = None
    genel_accuracy_pct: float | None = None
    genel_exams: int | None = None
    legacy_rows: int | None = None
    legacy_accuracy_pct: float | None = None
    combined_accuracy_pct: float | None = None
    # Ek açılar (2026-10-20)
    best_net_pct: float | None = None
    best_date: str | None = None
    worst_net_pct: float | None = None
    worst_date: str | None = None
    stdev_net_pct: float | None = None
    consistency: Literal["high", "mid", "low"] | None = None
    momentum: float | None = None
    momentum_window: int | None = None
    penalty: int = 4
    avg_net: float | None = None
    avg_questions: float | None = None
    lost_wrong_per_exam: float | None = None
    lost_blank_per_exam: float | None = None
    first_date: str | None = None
    last_date: str | None = None
    avg_gap_days: float | None = None
    days_since_last: int | None = None
    points: list[DenemeAnalysisPoint] = []


class DenemeAnalysisFlag(BaseModel):
    code: str
    series: str
    level: Literal["info", "warn"]
    text: str


class DenemeAnalysisSummary(BaseModel):
    with_result: int
    pending: int
    series_count: int
    branch_series: int


class DenemeOverviewPick(BaseModel):
    key: str
    label: str
    value: float


class DenemeOverviewWeek(BaseModel):
    week_start: str
    count: int
    subjects: int
    avg_net_pct: float | None = None


class DenemeOverview(BaseModel):
    exams: int = 0
    subjects: int = 0
    questions: int = 0
    correct: int = 0
    wrong: int = 0
    blank: int = 0
    accuracy_pct: float | None = None
    blank_rate_pct: float | None = None
    avg_net_pct: float | None = None
    lost_wrong: float = 0
    lost_blank: int = 0
    strongest: DenemeOverviewPick | None = None
    weakest: DenemeOverviewPick | None = None
    rising: DenemeOverviewPick | None = None
    falling: DenemeOverviewPick | None = None
    steadiest: DenemeOverviewPick | None = None
    weeks: list[DenemeOverviewWeek] = []


class DenemeAnalysisResponse(BaseModel):
    overview: DenemeOverview | None = None
    generated_for: str
    compare_days: int
    summary: DenemeAnalysisSummary
    series: list[DenemeAnalysisSeries]
    flags: list[DenemeAnalysisFlag]


@router.get("/students/{student_id}/deneme-analysis", response_model=DenemeAnalysisResponse)
def deneme_analysis(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """D4 — program denemelerinin ders/seri bazında analizi (salt okuma, kredisiz)."""
    from app.services.deneme_analysis import build_deneme_analysis

    student = _get_owned_student(db, student_id, user.id)
    return build_deneme_analysis(db, student)


@router.get("/students/{student_id}/deneme-pending", response_model=DenemePendingResponse)
def deneme_pending(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Çözülmüş ama sonucu girilmemiş denemeler (D3) — koç öğrenci sayfasında görür."""
    student = _get_owned_student(db, student_id, user.id)
    return build_pending_response(db, student.id)


@router.post("/students/{student_id}/pool/deneme-items")
def add_pool_deneme(
    student_id: int,
    body: PoolDenemeBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    from app.routes.api_v2.pool import _bundle_mut, _http, _open_or_404
    from app.routes.api_v2.teacher import _parse_iso_date
    from app.services import pool_mode as pm
    from app.services.pool_mode import PoolError

    student = _get_owned_student(db, student_id, user.id)
    period = _open_or_404(db, student)
    name = (body.name or "").strip() or None
    kw: dict = dict(quantity=body.count, unit=pm.UNIT_DENEME, question_count=body.question_count,
                    created_by=user, teacher_homework=body.teacher_homework,
                    day_hint=_parse_iso_date(body.day_hint) if body.day_hint else None)
    if body.book_id is not None:
        book = _assigned_deneme_book(db, student, body.book_id)
        picked = ds.pick_sections(db, student, book, 1)
        if not picked:
            raise _err("book_has_no_sections", "Bu deneme kitabının bölümü yok — önce denemeleri ekleyin.")
        if (body.question_count and not book.avg_questions_per_test
                and ds.question_count_from_label(picked[0][0].label) is None):
            book.avg_questions_per_test = body.question_count
        kw.update(subject=book.subject, book=book, section=picked[0][0])
        if book.type == ds.DENEME_BOOK_TYPES[1]:
            kw["exam_kind"] = ds.EXAM_KIND_GENEL
    elif body.kind == ds.EXAM_KIND_BRANS:
        if body.subject_id is None:
            raise _err("subject_required", "Branş denemesi için ders seçin.")
        subj = {s.id: s for s in _student_subjects(db, student, user.id)}.get(body.subject_id)
        if subj is None:
            raise _err("subject_not_found", "Seçilen ders bu öğrencinin dersleri arasında değil.")
        kw.update(subject=subj, label=name or f"{subj.name} branş denemesi", exam_kind=ds.EXAM_KIND_BRANS)
    else:
        preset = next((p for p in ds.genel_presets_for(student) if p.key == body.genel_key), None)
        if preset is None:
            raise _err("genel_key_required", "Genel deneme türünü seçin.")
        kw.update(subject=None, label=name or preset.label, exam_kind=ds.EXAM_KIND_GENEL,
                  exam_section=preset.exam_section,
                  question_count=body.question_count or preset.question_count)
    try:
        pm.add_item(db, period=period, student=student, **kw)
    except PoolError as e:
        raise _http(e)
    return _bundle_mut(db, user, student)
