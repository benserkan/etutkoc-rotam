"""Haftalık İskelet — API v2 (koç, F1 2026-09-25).

İskelet = "hangi gün hangi ders" kalıbı (öğrenci başına tek). Program
haftasında iskeletteki dersin görevi yoksa HAYALET hücre çıkar; hayalet görev
değildir, rezerv tutmaz. Koç çipe tıklayınca normal TEST görevi oluşur (rezerv
o anda açılır). Çipler canlı hesaplanır — ayrıntı services/skeleton_suggest.

Sahiplik dışı her şey 404. Öğrenci/veli iskeleti görmez.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Book, BookSection, StudentBook, Subject, User
from app.models.weekly_skeleton import (
    ROUTINE_MODES,
    ROUTINE_SCOPES,
    SkeletonGhostAction,
    WeeklySkeletonSlot,
)
from app.routes.api_v2.dependencies import assert_active_coaching
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.teacher import TaskCreateBody, TaskItemBody
from app.routes.api_v2.schemas.weekly_skeleton import (
    GhostAcceptanceReport,
    GhostAcceptBody,
    GhostAcceptResult,
    GhostActionBody,
    GhostRoutineBody,
    RoutinePreviewItem,
    RoutinePreviewTask,
    GhostsResponse,
    PeriodCreateBody,
    PeriodUpdateBody,
    SkeletonBookOption,
    SkeletonCopyBody,
    SkeletonCopyBookRef,
    SkeletonCopyCandidate,
    SkeletonCopyCandidatesResponse,
    SkeletonCopyResult,
    SkeletonCopyStudentResult,
    SkeletonDeleteBody,
    SkeletonPeriodItem,
    SkeletonFromWeekBody,
    SkeletonResponse,
    SkeletonSaveBody,
    SkeletonSlotOut,
    SkeletonSubjectOption,
    SpreadApplyBody,
    SpreadPreview,
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
from app.services import topic_spread
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


def _is_bank(b: Book) -> bool:
    return getattr(b.type, "value", b.type) == sk.BANK_TYPE


def _problem_book_ids(db: Session, books: list[Book]) -> set[int]:
    """Problem bölümü olan SORU BANKALARI (problem rutininin kaynak adayları)."""
    from app.models import Topic

    banks = [b.id for b in books if _is_bank(b)]
    if not banks:
        return set()
    rows = (
        db.query(BookSection)
        .filter(BookSection.book_id.in_(banks))
        .order_by(BookSection.book_id, BookSection.order, BookSection.id)
        .all()
    )
    tids = {r.topic_id for r in rows if r.topic_id}
    names = {int(i): n for i, n in db.query(Topic.id, Topic.name).filter(Topic.id.in_(tids or {0}))}
    by_book: dict[int, list] = {}
    for r in rows:
        by_book.setdefault(r.book_id, []).append(sk._Sec(
            id=r.id, book_id=r.book_id, book_name="", subject_id=0, label=r.label or "",
            order=r.order or 0, topic_id=r.topic_id, total=0, completed=0, reserved=0,
        ))
    prob = sk.problem_section_ids(by_book, names)
    return {b for b, lst in by_book.items() if any(x.id in prob for x in lst)}


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _periods(skels) -> list[SkeletonPeriodItem]:
    today_sk = sk.skeleton_for_date(skels, date.today())
    return [
        SkeletonPeriodItem(
            id=x.id, name=x.name, valid_from=_iso(x.valid_from),
            valid_until=_iso(sk.valid_until(skels, x)), slot_count=len(x.slots),
            is_current=today_sk is not None and today_sk.id == x.id, source=x.source,
        )
        for x in skels
    ]


def _build_response(
    db: Session, student: User, coach_id: int, skeleton_id: int | None = None,
    at: date | None = None,
) -> SkeletonResponse:
    """skeleton_id verilirse o dönem, yoksa `at` (varsayılan bugün) günü geçerli dönem."""
    options = _subject_options(db, student, coach_id)
    names = {s.id: s.name for s in options}
    book_opts = _book_options(db, student)
    prob_books = _problem_book_ids(db, book_opts)
    books = [
        SkeletonBookOption(
            id=b.id, name=b.name, subject_id=b.subject_id,
            book_type=getattr(b.type, "value", None), is_bank=_is_bank(b),
            has_problems=b.id in prob_books,
        )
        for b in book_opts
    ]
    book_names = {b.id: b.name for b in book_opts}
    skels = sk.list_skeletons(db, student.id)
    skel = sk.get_skeleton(db, student.id, at=at, skeleton_id=skeleton_id)
    if skel is None:
        return SkeletonResponse(
            exists=False,
            subjects=[SkeletonSubjectOption(id=s.id, name=s.name) for s in options],
            books=books,
            periods=_periods(skels),
        )
    missing_books = (
        {s.book_id for s in skel.slots if s.book_id}
        | {s.second_book_id for s in skel.slots if s.second_book_id}
    ) - set(book_names)
    if missing_books:
        for b in db.query(Book).filter(Book.id.in_(missing_books)):
            book_names[b.id] = b.name
    missing = {s.subject_id for s in skel.slots} - set(names)
    if missing:
        for s in db.query(Subject).filter(Subject.id.in_(missing)):
            names[s.id] = s.name
    return SkeletonResponse(
        exists=True,
        id=skel.id,
        name=skel.name,
        source=skel.source,
        valid_from=_iso(skel.valid_from),
        valid_until=_iso(sk.valid_until(skels, skel)),
        periods=_periods(skels),
        capacity=topic_spread.capacity_table(db, student, skel),
        slots=[
            SkeletonSlotOut(
                id=s.id, weekday=s.weekday, period=s.period, subject_id=s.subject_id,
                subject_name=names.get(s.subject_id, "?"), position=s.position,
                is_routine=s.is_routine, default_count=s.default_count,
                book_id=s.book_id, book_name=book_names.get(s.book_id) if s.book_id else None,
                label=s.label, routine_mode=s.routine_mode, is_anchor=bool(s.is_anchor),
                routine_scope=s.routine_scope, second_book_id=s.second_book_id,
                second_book_name=book_names.get(s.second_book_id) if s.second_book_id else None,
            )
            for s in sorted(skel.slots, key=lambda x: (x.weekday, x.position, x.id))
        ],
        subjects=[SkeletonSubjectOption(id=s.id, name=s.name) for s in options],
        books=books,
    )


def _validated_slots(db: Session, student: User, coach_id: int, slots) -> list[dict]:
    allowed = {s.id for s in _subject_options(db, student, coach_id)}
    opts = _book_options(db, student)
    book_subj = {b.id: b.subject_id for b in opts}
    banks = {b.id for b in opts if _is_bank(b)}
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
        scope = s.routine_scope or None
        if scope is not None and scope not in ROUTINE_SCOPES:
            raise _err(422, "bad_routine_scope", "Rutin kapsamı 'book' ya da 'problems' olmalı.")
        if not (s.is_routine and s.book_id) or scope == "book":
            scope = None
        second = s.second_book_id
        if second is not None:
            if second not in book_subj:
                raise _err(422, "book_not_allowed", "2. kaynak öğrencinin kitaplığında değil.")
            if second not in banks:
                raise _err(422, "second_not_bank",
                           "2. kaynak soru bankası olmalı (konu anlatımlı / video defter olamaz).")
            if book_subj[second] != s.subject_id:
                raise _err(422, "book_subject_mismatch", "2. kaynak satırın dersine ait değil.")
            if second == s.book_id:
                raise _err(422, "second_same_book", "2. kaynak satırın kitabıyla aynı olamaz.")
            if s.is_routine:
                second = None
        label = (s.label or "").strip()[:160] or None
        out.append({
            "weekday": s.weekday, "period": _validate_period(s.period),
            "subject_id": s.subject_id, "position": s.position if s.position else i,
            "is_routine": s.is_routine, "default_count": s.default_count,
            "book_id": s.book_id, "label": None if s.book_id else label,
            "routine_mode": mode, "is_anchor": bool(s.is_anchor),
            "routine_scope": scope, "second_book_id": second,
        })
    return out


# ---------------------------------------------------------------- iskelet


def _owned_skeleton(db: Session, student: User, skeleton_id: int | None):
    if skeleton_id is None:
        return None
    skel = sk.get_skeleton(db, student.id, skeleton_id=skeleton_id)
    if skel is None:
        raise _err(404, "skeleton_not_found", "Dönem bulunamadı.")
    return skel


def _period_conflict(e: Exception) -> HTTPException:
    return _err(409, "period_start_taken", str(e))


@router.get("/students/{student_id}/skeleton", response_model=SkeletonResponse)
def get_skeleton(
    student_id: int, skeleton_id: int | None = Query(None), at: str | None = Query(None),
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Varsayılan: bugün geçerli dönem. skeleton_id ile belirli dönem, at ile o
    günün dönemi. Yanıt tüm dönemlerin listesini (periods) de taşır."""
    student = _get_owned_student(db, student_id, user.id)
    if skeleton_id is not None:
        _owned_skeleton(db, student, skeleton_id)
    return _build_response(
        db, student, user.id, skeleton_id=skeleton_id,
        at=_parse_iso_date(at) if at else None,
    )


@router.post("/students/{student_id}/skeleton", response_model=MutationResponse[SkeletonResponse])
def save_skeleton(
    student_id: int, body: SkeletonSaveBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    student = _get_owned_student(db, student_id, user.id)
    target = _owned_skeleton(db, student, body.skeleton_id)
    slots = _validated_slots(db, student, user.id, body.slots)
    skel = sk.replace_slots(
        db, student=student, coach_id=user.id, slots=slots, name=body.name, skeleton=target,
    )
    if body.day_capacity is not None:
        topic_spread.set_capacity_overrides(skel, body.day_capacity)
    db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id, skeleton_id=skel.id),
        invalidate=[_key(user.id, student.id)],
    )


@router.post("/students/{student_id}/skeleton/from-week", response_model=MutationResponse[SkeletonResponse])
def skeleton_from_week(
    student_id: int, body: SkeletonFromWeekBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Bir haftanın (≤14 gün) görevlerinden iskelet. mode=replace: seçili (yoksa
    bugün geçerli) dönemin satırlarını değiştirir · mode=new: haftanın ilk
    gününden YENİ DÖNEM başlatır (önceki dönem silinmez, bir gün önce biter)."""
    student = _get_owned_student(db, student_id, user.id)
    start = _parse_iso_date(body.start)
    end = _parse_iso_date(body.end)
    if end < start:
        raise _err(422, "bad_range", "Bitiş tarihi başlangıçtan önce olamaz.")
    if body.mode not in ("replace", "new"):
        raise _err(422, "bad_mode", "Geçersiz seçim.")
    target = _owned_skeleton(db, student, body.skeleton_id)
    slots = sk.slots_from_tasks(db, student=student, coach_id=user.id, start=start, end=end)
    if not slots:
        raise _err(422, "empty_week", "Bu tarih aralığında iskelet çıkarılacak görev yok.")
    try:
        if body.mode == "new":
            target = sk.create_period(
                db, student=student, coach_id=user.id, valid_from=start, name=body.name,
                source="from_week",
            )
        skel = sk.replace_slots(
            db, student=student, coach_id=user.id, slots=slots, source="from_week",
            skeleton=target, name=body.name if body.mode == "replace" else None,
        )
    except sk.PeriodConflict as e:
        db.rollback()
        raise _period_conflict(e)
    db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id, skeleton_id=skel.id),
        invalidate=[_key(user.id, student.id)],
    )


@router.post("/students/{student_id}/skeleton/delete", response_model=MutationResponse[SkeletonResponse])
def delete_skeleton(
    student_id: int, body: SkeletonDeleteBody | None = Body(None),
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Bir dönemi sil (gövdesiz: bugün geçerli dönem). Görevlere dokunulmaz."""
    student = _get_owned_student(db, student_id, user.id)
    sid_ = body.skeleton_id if body else None
    skel = _owned_skeleton(db, student, sid_) if sid_ else sk.get_skeleton(db, student.id)
    if skel is not None:
        db.delete(skel)
        db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id), invalidate=[_key(user.id, student.id)],
    )


@router.post("/students/{student_id}/skeleton/periods",
             response_model=MutationResponse[SkeletonResponse])
def create_period(
    student_id: int, body: PeriodCreateBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Yeni dönem: boş ya da başka bir dönemin kopyası (yarıyıl tatilinde yaz
    iskeletini yeniden kullanmak gibi)."""
    student = _get_owned_student(db, student_id, user.id)
    src = _owned_skeleton(db, student, body.copy_from_id)
    try:
        skel = sk.create_period(
            db, student=student, coach_id=user.id, valid_from=_parse_iso_date(body.valid_from),
            name=body.name, copy_from=src,
        )
    except sk.PeriodConflict as e:
        db.rollback()
        raise _period_conflict(e)
    db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id, skeleton_id=skel.id),
        invalidate=[_key(user.id, student.id)],
    )


@router.post("/students/{student_id}/skeleton/periods/{skeleton_id}",
             response_model=MutationResponse[SkeletonResponse])
def update_period(
    student_id: int, skeleton_id: int, body: PeriodUpdateBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Dönem adını ya da başlangıcını değiştir."""
    student = _get_owned_student(db, student_id, user.id)
    skel = _owned_skeleton(db, student, skeleton_id)
    try:
        sk.update_period(
            db, student=student, skeleton=skel, name=body.name,
            valid_from=_parse_iso_date(body.valid_from) if body.valid_from else None,
            clear_start=body.clear_start,
        )
    except sk.PeriodConflict as e:
        db.rollback()
        raise _period_conflict(e)
    db.commit()
    return MutationResponse[SkeletonResponse](
        data=_build_response(db, student, user.id, skeleton_id=skel.id),
        invalidate=[_key(user.id, student.id)],
    )


# ------------------------------------------------ başka öğrencilere kopyala


def _grade_label(u: User) -> str:
    if u.is_graduate:
        return "Mezun"
    return f"{u.grade_level}. sınıf" if u.grade_level else "Sınıf yok"


@router.get("/students/{student_id}/skeleton/copy-candidates",
            response_model=SkeletonCopyCandidatesResponse)
def skeleton_copy_candidates(
    student_id: int, skeleton_id: int = Query(...),
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Kopyalama penceresi: kaynak dönem + koçun diğer AKTİF öğrencileri (şube,
    mevcut dönemleri, kaynaktaki kitaplardan hangileri öğrencide yok). Salt okuma."""
    from app.models import UserRole
    from app.services import skeleton_copy as sc

    student = _get_owned_student(db, student_id, user.id)
    src = _owned_skeleton(db, student, skeleton_id)
    targets = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT,
                User.is_active.is_(True), User.id != student.id)
        .order_by(User.class_group, User.full_name)
        .all()
    )
    plans = sc.plan_targets(db, source=src, targets=targets, mode="replace", valid_from=None)
    book_ids = sc._source_book_ids(src)
    names = {int(i): n for i, n in db.query(Book.id, Book.name).filter(Book.id.in_(book_ids or {0}))}
    out = []
    for p in plans:
        skels = sk.list_skeletons(db, p.student.id)
        out.append(SkeletonCopyCandidate(
            student_id=p.student.id, full_name=p.student.full_name,
            grade_label=_grade_label(p.student), class_group=p.student.class_group,
            period_count=p.period_count,
            period_starts=[x.valid_from.isoformat() if x.valid_from else None for x in skels],
            current_period_name=p.replaced_name, current_slot_count=p.replaced_slot_count,
            missing_books=[SkeletonCopyBookRef(id=b, name=names.get(b, "?")) for b in p.missing_book_ids],
        ))
    return SkeletonCopyCandidatesResponse(
        source_skeleton_id=src.id, source_name=src.name,
        source_valid_from=src.valid_from.isoformat() if src.valid_from else None,
        source_slot_count=len(src.slots),
        source_books=[SkeletonCopyBookRef(id=b, name=names.get(b, "?")) for b in sorted(book_ids)],
        candidates=out,
    )


@router.post("/students/{student_id}/skeleton/copy",
             response_model=MutationResponse[SkeletonCopyResult])
def skeleton_copy(
    student_id: int, body: SkeletonCopyBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Kaynak dönemi seçili öğrencilere kopyala (bkz. services/skeleton_copy)."""
    from app.models import UserRole
    from app.services import skeleton_copy as sc

    if body.mode not in sc.COPY_MODES:
        raise _err(422, "bad_copy_mode", "Kopyalama biçimi 'new' ya da 'replace' olmalı.")
    valid_from = _parse_iso_date(body.valid_from) if body.valid_from else None
    if body.mode == "new" and valid_from is None:
        raise _err(422, "valid_from_required", "Yeni dönem için başlangıç tarihi gerekli.")
    student = _get_owned_student(db, student_id, user.id)
    src = _owned_skeleton(db, student, body.skeleton_id)
    requested = list(dict.fromkeys(int(x) for x in body.target_ids if int(x) != student.id))
    found = {
        u.id: u for u in db.query(User).filter(
            User.teacher_id == user.id, User.role == UserRole.STUDENT,
            User.id.in_(requested or [0]),
        )
    }
    invalid = [i for i in requested if i not in found]
    targets = [found[i] for i in requested if i in found]
    plans = sc.plan_targets(db, source=src, targets=targets, mode=body.mode, valid_from=valid_from)
    rows = sc.apply_copy(
        db, source=src, coach_id=user.id, plans=plans, mode=body.mode, valid_from=valid_from,
        name=body.name, assign_missing_books=body.assign_missing_books,
    )
    db.commit()
    keys: list[str] = []
    for r in rows:
        keys.append(_key(user.id, r["student_id"]))
        if r["books_assigned"]:
            keys += [f"teacher:{user.id}:students:{r['student_id']}",
                     f"teacher:{user.id}:library:books"]
    return MutationResponse[SkeletonCopyResult](
        data=SkeletonCopyResult(
            students=[SkeletonCopyStudentResult(**r) for r in rows],
            skipped_invalid_ids=invalid,
        ),
        invalidate=keys,
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
    kalemli olabilir); as_activity → kitapsız satırın etiketiyle ETKİNLİK.
    Kalemler birden çok kitaba yayılırsa (problem rutini kaynak değiştirirken)
    kitap başına ayrı görev yazılır. Dönüş: görev listesi."""
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
        return [task]
    if not items:
        raise _err(422, "no_items", "Görev için bölüm seçilmedi.")
    per_book: dict[int, list[TaskItemBody]] = {}
    first_sec = None
    for section_id, count in items:
        sec = db.get(BookSection, section_id)
        if sec is None:
            raise _err(404, "section_not_found", "Bölüm bulunamadı.")
        book = db.get(Book, sec.book_id)
        if book is None or book.subject_id != slot.subject_id:
            raise _err(422, "subject_mismatch", "Bu bölüm iskeletteki derse ait değil.")
        first_sec = first_sec or sec
        per_book.setdefault(sec.book_id, []).append(TaskItemBody(
            book_id=sec.book_id, section_id=sec.id, planned_count=count,
            allow_over_capacity=True,
        ))
    tasks = []
    for body_items in per_book.values():
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
        tasks.append(task)
    db.add(SkeletonGhostAction(
        student_id=student.id, slot_id=slot.id, coach_id=user.id, date=d,
        action="accepted" if chip_rank else "other",
        chip_rank=chip_rank, chip_kind=chip_kind, chip_count=chip_count,
        section_id=first_sec.id, topic_id=first_sec.topic_id, task_id=tasks[0].id,
    ))
    return tasks


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
        tasks = _accept(
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
    inv: list[str] = []
    for t in tasks:
        for k in _invalidate_for_task(t, user.id):
            if k not in inv:
                inv.append(k)
    return MutationResponse[GhostAcceptResult](
        data=GhostAcceptResult(task_ids=[t.id for t in tasks], created=len(tasks)),
        invalidate=inv,
        warnings=warnings,
    )


def _routine_preview(db: Session, tasks: list) -> list[RoutinePreviewTask]:
    """Henüz commit edilmemiş (geri alınacak) rutin görevlerinden önizleme satırları."""
    out: list[RoutinePreviewTask] = []
    for t in tasks:
        db.refresh(t)
        items = []
        subj_name = ""
        for it in t.book_items:
            items.append(RoutinePreviewItem(
                book_name=it.book.name if it.book else it.label,
                section_label=it.section.label if it.section else None,
                count=it.planned_count or 0,
            ))
            if not subj_name and it.book is not None:
                s_ = db.get(Subject, it.book.subject_id)
                subj_name = s_.name if s_ else ""
        if not subj_name and " · " in (t.title or ""):
            subj_name = t.title.split(" · ", 1)[0]
        planned = sum(i.count for i in items)
        out.append(RoutinePreviewTask(
            date=t.date.isoformat(), subject_name=subj_name, title=t.title or "",
            planned=planned, is_activity=not items,
            too_many=planned > sk.ROUTINE_WARN_COUNT, items=items,
        ))
    out.sort(key=lambda x: (x.date, x.subject_name))
    return out


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
                    tasks.extend(_accept(
                        db, user=user, student=student, slot=slot, d=d, items=items,
                        chip_rank=1, chip_kind=c["kind"], chip_count=len(g["chips"]),
                        warnings=warnings,
                    ))
                elif slot.label and not slot.book_id:
                    tasks.extend(_accept(
                        db, user=user, student=student, slot=slot, d=d, items=[],
                        chip_rank=1, chip_kind="activity", chip_count=0,
                        warnings=warnings, as_activity=True,
                    ))
            db.flush()
            d += timedelta(days=1)
        preview = _routine_preview(db, tasks) if body.dry_run else []
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        db.rollback()
        raise
    if body.dry_run:
        db.rollback()
        return MutationResponse[GhostAcceptResult](
            data=GhostAcceptResult(created=len(preview), preview=preview),
            invalidate=[], warnings=warnings,
        )
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


# ---------------------------------------------------------------- konuyu yay (F2-3)


@router.get("/students/{student_id}/topic-spread", response_model=SpreadPreview)
def topic_spread_preview(
    student_id: int, start: str = Query(...), per_day: int = Query(3, ge=1, le=50),
    topic_id: int | None = Query(None), section_id: int | None = Query(None),
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Konunun kalan testlerini günlere yayma ÖNİZLEMESİ (yazmaz). Çapa günlerinin
    payı önceden ayrılır; bir sonraki aynı dersin çapa gününden önce biter."""
    student = _get_owned_student(db, student_id, user.id)
    if topic_id is None and section_id is None:
        raise _err(422, "topic_required", "Konu ya da bölüm seçilmeli.")
    return topic_spread.plan_spread(
        db, student=student, coach_id=user.id, start=_parse_iso_date(start),
        per_day=per_day, topic_id=topic_id, section_id=section_id,
    )


@router.post("/students/{student_id}/topic-spread",
             response_model=MutationResponse[GhostAcceptResult])
def topic_spread_apply(
    student_id: int, body: SpreadApplyBody,
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    """Önizlemede onaylanan (koçun düzelttiği) yaymayı yaz: gün × kitap başına
    bir TEST görevi. İleri tarihli görevler taslak iner (akıllı varsayılan)."""
    from collections import defaultdict as _dd

    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    owned_books = {
        b for (b,) in db.query(StudentBook.book_id).filter(StudentBook.student_id == student.id)
    }
    today = date.today()
    warnings: list[str] = []
    tasks = []
    try:
        for day in body.days:
            d = _parse_iso_date(day.date)
            if d < today:
                raise _err(422, "past_date", "Geçmiş güne yayılamaz.")
            per_book: dict[int, list] = _dd(list)
            for it in day.items:
                sec = db.get(BookSection, it.section_id)
                if sec is None or sec.book_id not in owned_books:
                    raise _err(404, "section_not_found", "Bölüm bulunamadı.")
                per_book[sec.book_id].append(TaskItemBody(
                    book_id=sec.book_id, section_id=sec.id, planned_count=it.count,
                    allow_over_capacity=True,
                ))
            for _book_id, items in per_book.items():
                task = _create_task_with_items(
                    db, student=student,
                    payload=TaskCreateBody(date=d.isoformat(), type="test", title="Görev", items=items),
                    overflow_out=warnings,
                )
                if len(items) > 1:
                    from app.services.task_titles import refresh_auto_title

                    db.flush()
                    db.refresh(task)
                    task.title = "Görev"
                    refresh_auto_title(task)
                db.flush()
                tasks.append(task)
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


@router.get("/skeleton/acceptance", response_model=GhostAcceptanceReport)
def acceptance(days: int = Query(30, ge=1, le=180), user: User = Depends(_require_teacher),
               db: Session = Depends(get_db)):
    """F1 başarı ölçüsü — koçun kendi hayalet kabul oranı."""
    return sk.acceptance_report(db, coach_id=user.id, days=days)
