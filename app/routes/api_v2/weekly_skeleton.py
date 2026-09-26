"""Haftalık İskelet — API v2 (koç, F1 2026-09-25).

İskelet = "hangi gün hangi ders" kalıbı (öğrenci başına tek). Program
haftasında iskeletteki dersin görevi yoksa HAYALET hücre çıkar; hayalet görev
değildir, rezerv tutmaz. Koç çipe tıklayınca normal TEST görevi oluşur (rezerv
o anda açılır). Çipler canlı hesaplanır — ayrıntı services/skeleton_suggest.

Sahiplik dışı her şey 404. Öğrenci/veli iskeleti görmez.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Book, BookSection, StudentBook, Subject, User
from app.models.weekly_skeleton import ROUTINE_MODES, SkeletonGhostAction, WeeklySkeletonSlot
from app.routes.api_v2.dependencies import assert_active_coaching
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.teacher import TaskCreateBody, TaskItemBody
from app.routes.api_v2.schemas.weekly_skeleton import (
    GhostAcceptanceReport,
    GhostAcceptBody,
    GhostAcceptResult,
    GhostActionBody,
    GhostRoutineBody,
    GhostsResponse,
    SkeletonBookOption,
    SkeletonFromWeekBody,
    SkeletonResponse,
    SkeletonSaveBody,
    SkeletonSlotOut,
    SkeletonSubjectOption,
)
from app.routes.api_v2.teacher import (
    _create_task_with_items,
    _get_owned_student,
    _invalidate_for_task,
    _parse_iso_date,
    _require_teacher,
    _reservation_to_http,
    _validate_period,
)
from app.services import skeleton_suggest as sk
from app.services.gorev_stats import is_test_book
from app.services.task_service import ReservationError

router = APIRouter(prefix="/teacher", tags=["v2-weekly-skeleton"])


def _err(status: int, code: str, message: str) -> HTTPException:
    kind = {404: "not_found", 409: "conflict", 422: "validation"}.get(status, "error")
    return HTTPException(status_code=status, detail={"error": kind, "code": code, "message": message})


def _key(tid: int, sid: int) -> str:
    return f"teacher:{tid}:students:{sid}:skeleton"


def _subject_options(db: Session, student: User, coach_id: int) -> list[Subject]:
    from app.services.curriculum_progress import _applicable_subjects

    subs = {s.id: s for s in _applicable_subjects(db, student, coach_id)}
    # Öğrencinin kitaplarının dersleri de seçilebilir (müfredat dışı kaynak).
    for s in (
        db.query(Subject)
        .join(Book, Book.subject_id == Subject.id)
        .join(StudentBook, StudentBook.book_id == Book.id)
        .filter(StudentBook.student_id == student.id, StudentBook.archived_at.is_(None))
        .all()
    ):
        subs.setdefault(s.id, s)
    return sorted(subs.values(), key=lambda s: ((s.order or 0), s.name))


def _book_options(db: Session, student: User) -> list[Book]:
    """Satıra bağlanabilecek kitaplar: öğrencinin arşivlenmemiş TEST kitapları."""
    books = (
        db.query(Book)
        .join(StudentBook, StudentBook.book_id == Book.id)
        .filter(StudentBook.student_id == student.id, StudentBook.archived_at.is_(None))
        .all()
    )
    return sorted((b for b in books if is_test_book(b)), key=lambda b: b.name)


def _build_response(db: Session, student: User, coach_id: int) -> SkeletonResponse:
    options = _subject_options(db, student, coach_id)
    names = {s.id: s.name for s in options}
    book_opts = _book_options(db, student)
    books = [SkeletonBookOption(id=b.id, name=b.name, subject_id=b.subject_id) for b in book_opts]
    book_names = {b.id: b.name for b in book_opts}
    skel = sk.get_skeleton(db, student.id)
    if skel is None:
        return SkeletonResponse(
            exists=False,
            subjects=[SkeletonSubjectOption(id=s.id, name=s.name) for s in options],
            books=books,
        )
    missing_books = {s.book_id for s in skel.slots if s.book_id} - set(book_names)
    if missing_books:
        for b in db.query(Book).filter(Book.id.in_(missing_books)):
            book_names[b.id] = b.name
    missing = {s.subject_id for s in skel.slots} - set(names)
    if missing:
        for s in db.query(Subject).filter(Subject.id.in_(missing)):
            names[s.id] = s.name
    return SkeletonResponse(
        exists=True,
        name=skel.name,
        source=skel.source,
        slots=[
            SkeletonSlotOut(
                id=s.id, weekday=s.weekday, period=s.period, subject_id=s.subject_id,
                subject_name=names.get(s.subject_id, "?"), position=s.position,
                is_routine=s.is_routine, default_count=s.default_count,
                book_id=s.book_id, book_name=book_names.get(s.book_id) if s.book_id else None,
                label=s.label, routine_mode=s.routine_mode,
            )
            for s in sorted(skel.slots, key=lambda x: (x.weekday, x.position, x.id))
        ],
        subjects=[SkeletonSubjectOption(id=s.id, name=s.name) for s in options],
        books=books,
    )


def _validated_slots(db: Session, student: User, coach_id: int, slots) -> list[dict]:
    allowed = {s.id for s in _subject_options(db, student, coach_id)}
    book_subj = {b.id: b.subject_id for b in _book_options(db, student)}
    out = []
    for i, s in enumerate(slots):
        if s.subject_id not in allowed:
            raise _err(422, "subject_not_allowed", "Bu ders öğrencinin derslerinden biri değil.")
        if s.book_id is not None:
            if s.book_id not in book_subj:
                raise _err(422, "book_not_allowed", "Bu kitap öğrencinin kitaplığında değil.")
            if book_subj[s.book_id] != s.subject_id:
                raise _err(422, "book_subject_mismatch", "Kitap satırın dersine ait değil.")
        mode = s.routine_mode or None
        if mode is not None and mode not in ROUTINE_MODES:
            raise _err(422, "bad_routine_mode", "Rutin biçimi 'sirali' ya da 'karma' olmalı.")
        if not (s.is_routine and s.book_id):
            mode = None
        elif mode is None:
            mode = "sirali"
        label = (s.label or "").strip()[:160] or None
        out.append({
            "weekday": s.weekday, "period": _validate_period(s.period),
            "subject_id": s.subject_id, "position": s.position if s.position else i,
            "is_routine": s.is_routine, "default_count": s.default_count,
            "book_id": s.book_id, "label": None if s.book_id else label,
            "routine_mode": mode,
        })
    return out


# ---------------------------------------------------------------- iskelet


@router.get("/students/{student_id}/skeleton", response_model=SkeletonResponse)
def get_skeleton(student_id: int, user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    return _build_response(db, student, user.id)


@router.post("/students/{student_id}/skeleton", response_model=MutationResponse[SkeletonResponse])
def save_skeleton(
    student_id: int, body: SkeletonSaveBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    student = _get_owned_student(db, student_id, user.id)
    slots = _validated_slots(db, student, user.id, body.slots)
    sk.replace_slots(db, student=student, coach_id=user.id, slots=slots, name=body.name)
    db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id), invalidate=[_key(user.id, student.id)],
    )


@router.post("/students/{student_id}/skeleton/from-week", response_model=MutationResponse[SkeletonResponse])
def skeleton_from_week(
    student_id: int, body: SkeletonFromWeekBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Bir haftanın (≤14 gün) görevlerinden iskelet üret — mevcut iskeleti değiştirir."""
    student = _get_owned_student(db, student_id, user.id)
    start = _parse_iso_date(body.start)
    end = _parse_iso_date(body.end)
    if end < start:
        raise _err(422, "bad_range", "Bitiş tarihi başlangıçtan önce olamaz.")
    slots = sk.slots_from_tasks(db, student=student, coach_id=user.id, start=start, end=end)
    if not slots:
        raise _err(422, "empty_week", "Bu tarih aralığında iskelet çıkarılacak görev yok.")
    sk.replace_slots(db, student=student, coach_id=user.id, slots=slots, source="from_week")
    db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id), invalidate=[_key(user.id, student.id)],
    )


@router.post("/students/{student_id}/skeleton/delete", response_model=MutationResponse[SkeletonResponse])
def delete_skeleton(student_id: int, user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    skel = sk.get_skeleton(db, student.id)
    if skel is not None:
        db.delete(skel)
        db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id), invalidate=[_key(user.id, student.id)],
    )


# ---------------------------------------------------------------- hayaletler


@router.get("/students/{student_id}/skeleton/ghosts", response_model=GhostsResponse)
def get_ghosts(
    student_id: int, start: str = Query(...), end: str = Query(...),
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    student = _get_owned_student(db, student_id, user.id)
    return sk.build_ghosts(
        db, student=student, coach_id=user.id,
        start=_parse_iso_date(start), end=_parse_iso_date(end),
    )


def _owned_slot(db: Session, student: User, slot_id: int) -> WeeklySkeletonSlot:
    slot = db.get(WeeklySkeletonSlot, slot_id)
    if slot is None or slot.skeleton.student_id != student.id:
        raise _err(404, "slot_not_found", "İskelet satırı bulunamadı.")
    return slot


def _accept(
    db: Session, *, user: User, student: User, slot: WeeklySkeletonSlot, d: date,
    items: list[tuple[int, int]], chip_rank: int | None, chip_kind: str | None,
    chip_count: int | None, warnings: list[str], as_activity: bool = False,
):
    """Hayaleti göreve çevir. items = [(section_id, adet)] (rutin çipi çok
    kalemli olabilir); as_activity → kitapsız satırın etiketiyle ETKİNLİK."""
    if as_activity:
        if not slot.label:
            raise _err(422, "no_label", "Bu satırın etkinlik adı yok.")
        subj = db.get(Subject, slot.subject_id)
        payload = TaskCreateBody(
            date=d.isoformat(), type="other",
            title=f"{subj.name if subj else ''} · {slot.label}".strip(" ·"),
            period=slot.period, items=[],
        )
        task = _create_task_with_items(db, student=student, payload=payload, overflow_out=warnings)
        db.flush()
        db.add(SkeletonGhostAction(
            student_id=student.id, slot_id=slot.id, coach_id=user.id, date=d,
            action="accepted", chip_rank=chip_rank or 1, chip_kind="activity",
            chip_count=chip_count, task_id=task.id,
        ))
        return task
    if not items:
        raise _err(422, "no_items", "Görev için bölüm seçilmedi.")
    body_items = []
    first_sec = None
    for section_id, count in items:
        sec = db.get(BookSection, section_id)
        if sec is None:
            raise _err(404, "section_not_found", "Bölüm bulunamadı.")
        book = db.get(Book, sec.book_id)
        if book is None or book.subject_id != slot.subject_id:
            raise _err(422, "subject_mismatch", "Bu bölüm iskeletteki derse ait değil.")
        first_sec = first_sec or sec
        body_items.append(TaskItemBody(
            book_id=sec.book_id, section_id=sec.id, planned_count=count,
            allow_over_capacity=True,
        ))
    payload = TaskCreateBody(
        date=d.isoformat(), type="test", title="Görev", period=slot.period, items=body_items,
    )
    task = _create_task_with_items(db, student=student, payload=payload, overflow_out=warnings)
    if len(body_items) > 1:
        # Çok kalemli görevde başlık kalemlerden türetilir ("Kitap — A: 1 test · B: 1 test")
        from app.services.task_titles import refresh_auto_title

        db.flush()
        db.refresh(task)
        task.title = "Görev"
        refresh_auto_title(task)
    db.flush()
    db.add(SkeletonGhostAction(
        student_id=student.id, slot_id=slot.id, coach_id=user.id, date=d,
        action="accepted" if chip_rank else "other",
        chip_rank=chip_rank, chip_kind=chip_kind, chip_count=chip_count,
        section_id=first_sec.id, topic_id=first_sec.topic_id, task_id=task.id,
    ))
    return task


@router.post("/students/{student_id}/skeleton/ghosts/accept",
             response_model=MutationResponse[GhostAcceptResult])
def accept_ghost(
    student_id: int, body: GhostAcceptBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Çip → normal TEST görevi (rezerv burada açılır; periyot iskeletten)."""
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    slot = _owned_slot(db, student, body.slot_id)
    d = _parse_iso_date(body.date)
    if d.weekday() != slot.weekday:
        raise _err(422, "weekday_mismatch", "Bu iskelet satırı o güne ait değil.")
    warnings: list[str] = []
    if body.items:
        items = [(it.section_id, it.count) for it in body.items]
    elif body.section_id is not None:
        items = [(body.section_id, body.count)]
    else:
        items = []
    try:
        task = _accept(
            db, user=user, student=student, slot=slot, d=d, items=items,
            chip_rank=body.chip_rank, chip_kind=body.chip_kind,
            chip_count=body.chip_count, warnings=warnings, as_activity=body.as_activity,
        )
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return MutationResponse[GhostAcceptResult](
        data=GhostAcceptResult(task_ids=[task.id], created=1),
        invalidate=_invalidate_for_task(task, user.id),
        warnings=warnings,
    )


@router.post("/students/{student_id}/skeleton/ghosts/accept-routine",
             response_model=MutationResponse[GhostAcceptResult])
def accept_routine(
    student_id: int, body: GhostRoutineBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """RUTİN hayaletleri topluca yaz. end verilirse date..end arası her gün
    SIRAYLA yazılır: her gün bir öncekinin kaldığı yerden devam eder (karışık
    paragraf rutini ertesi gün sonraki bölümlerden başlar)."""
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    d0 = _parse_iso_date(body.date)
    d1 = _parse_iso_date(body.end) if body.end else d0
    if d1 < d0:
        raise _err(422, "bad_range", "Bitiş tarihi başlangıçtan önce olamaz.")
    d1 = min(d1, d0 + timedelta(days=sk.MAX_RANGE_DAYS - 1))
    warnings: list[str] = []
    tasks = []
    try:
        d = d0
        while d <= d1:
            data = sk.build_ghosts(db, student=student, coach_id=user.id, start=d, end=d)
            for g in (g for day in data["days"] for g in day["ghosts"] if g["is_routine"]):
                slot = _owned_slot(db, student, g["slot_id"])
                if g["chips"]:
                    c = g["chips"][0]
                    items = (
                        [(it["section_id"], it["count"]) for it in c["items"]]
                        if c.get("items") else [(c["section_id"], c["count"])]
                    )
                    tasks.append(_accept(
                        db, user=user, student=student, slot=slot, d=d, items=items,
                        chip_rank=1, chip_kind=c["kind"], chip_count=len(g["chips"]),
                        warnings=warnings,
                    ))
                elif slot.label and not slot.book_id:
                    tasks.append(_accept(
                        db, user=user, student=student, slot=slot, d=d, items=[],
                        chip_rank=1, chip_kind="activity", chip_count=0,
                        warnings=warnings, as_activity=True,
                    ))
            db.flush()
            d += timedelta(days=1)
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    inv: list[str] = [_key(user.id, student.id)]
    for t in tasks:
        for k in _invalidate_for_task(t, user.id):
            if k not in inv:
                inv.append(k)
    return MutationResponse[GhostAcceptResult](
        data=GhostAcceptResult(task_ids=[t.id for t in tasks], created=len(tasks)),
        invalidate=inv, warnings=warnings,
    )


@router.post("/students/{student_id}/skeleton/ghosts/action",
             response_model=MutationResponse[GhostAcceptResult])
def ghost_action(
    student_id: int, body: GhostActionBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Hayaleti o gün için kaldır (dismissed) ya da geri getir (restore)."""
    student = _get_owned_student(db, student_id, user.id)
    slot = _owned_slot(db, student, body.slot_id)
    d = _parse_iso_date(body.date)
    if body.action == "dismissed":
        db.add(SkeletonGhostAction(
            student_id=student.id, slot_id=slot.id, coach_id=user.id, date=d, action="dismissed",
        ))
    elif body.action == "restore":
        db.query(SkeletonGhostAction).filter(
            SkeletonGhostAction.student_id == student.id,
            SkeletonGhostAction.slot_id == slot.id,
            SkeletonGhostAction.date == d,
            SkeletonGhostAction.action == "dismissed",
        ).delete(synchronize_session=False)
    else:
        raise _err(422, "bad_action", "Geçersiz işlem.")
    db.commit()
    return MutationResponse[GhostAcceptResult](
        data=GhostAcceptResult(), invalidate=[_key(user.id, student.id)],
    )


@router.get("/skeleton/acceptance", response_model=GhostAcceptanceReport)
def acceptance(days: int = Query(30, ge=1, le=180), user: User = Depends(_require_teacher),
               db: Session = Depends(get_db)):
    """F1 başarı ölçüsü — koçun kendi hayalet kabul oranı."""
    return sk.acceptance_report(db, coach_id=user.id, days=days)
