"""Haftalık görev havuzu — ÖĞRENCİ uçları (Adım 3, 2026-10-12; K34–K41).

Öğrenci havuzu görür, günün kabını kurar (kap = o güne mevcut görev → Bugün ekranında
işaretlenir, D/Y/B mevcut akışla girilir), yapamadığını havuza geri alır, kendi kalemini
ekler (onay bekler, K38). Yazma kuralları `pool_mode`'da. Anahtar: student:{id}:pool
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Book, BookSection, PoolItem, Subject, Task, TaskStatus, Topic, User
from app.models.pool import APPROVAL_REJECTED, POOL_UNITS, SOURCE_STUDENT
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.pool import (
    StudentCloseDayBody, StudentCupBody, StudentCupResizeBody, StudentCupTask, StudentPoolHint, StudentPoolItemBody,
    StudentPoolItemOut, StudentPoolProjectionDay, StudentPoolProjectionSubject, StudentPoolResponse, StudentPoolSubject,
    StudentPoolSummary,
)
from app.routes.api_v2.student import _require_student
from app.routes.api_v2.teacher import _parse_iso_date
from app.services import pool_mode as pm
from app.services.pool_mode import PoolError

router = APIRouter(prefix="/student", tags=["v2-pool-student"])


def _key(sid: int) -> str:
    return f"student:{sid}:pool"


def _day_keys(sid: int, d: date) -> list[str]:
    return [_key(sid), f"student:{sid}:day:{d.isoformat()}", f"student:{sid}:summary:{d.isoformat()}",
            f"student:{sid}:sidebar", f"student:{sid}:week"]


def _http(e: PoolError, status: int = 422) -> HTTPException:
    kind = {404: "not_found", 409: "conflict"}.get(status, "validation")
    return HTTPException(status_code=status, detail={"error": kind, "code": e.code, "message": e.message})


def _title(it: PoolItem, names: dict) -> str:
    sec = names["sections"].get(it.book_section_id) if it.book_section_id else None
    book = names["books"].get(it.book_id) if it.book_id else None
    top = names["topics"].get(it.topic_id) if it.topic_id else None
    if sec and book:
        return f"{book.name} — {sec.label}"
    if top:
        return top.name + (f" ({book.name})" if book else "")
    return it.label or "—"


def _pace(summary: pm.PeriodSummary, period_days_open: int) -> tuple[str, str]:
    """K41/K42 sade tempo cümlesi — yargılamaz."""
    if summary.total_units == 0:
        return "belirsiz", "Havuz boş."
    remaining = summary.total_units - summary.done_units
    if remaining <= 0:
        return "onde", "Havuzu bitirdin, kalan gün sana kaldı."
    if summary.days_left <= 1 and remaining > 0:
        return "geride", f"Seansa kadar {remaining} birim kaldı; bugün yapabildiğin kadarını yap."
    per_day = summary.per_day_needed
    if per_day <= 2:
        return "yolunda", f"Bu hızla {summary.days_left} günde biter: günde {per_day:g} birim yeter."
    return "geride", f"Günde {per_day:g} birim gerekiyor; bugün bir fazla yapmak haftayı rahatlatır."


def _previous_briefs(db: Session, student_id: int, period, today: date, limit: int = 8):
    """K60: öğrenci önceki dönemlerini görür (yüzde/birim; yargı yok)."""
    from app.models.pool import PERIOD_STATUS_LABELS
    from app.routes.api_v2.schemas.pool import PoolPeriodBrief
    out = []
    for p in pm.list_periods(db, student_id, limit=limit + 1):
        if period is not None and p.id == period.id:
            continue
        sm = pm.period_summary(db, p, today)
        out.append(PoolPeriodBrief(id=p.id, opened_on=p.opened_on.isoformat(),
                                   closed_on=p.closed_on.isoformat() if p.closed_on else None, status=p.status,
                                   status_label=PERIOD_STATUS_LABELS.get(p.status, p.status),
                                   total_units=sm.total_units, done_units=sm.done_units, pct=sm.pct))
    return out[:limit]


def _break_out(db: Session, student_id: int):
    from app.routes.api_v2.schemas.pool import PoolBreakOut
    br = pm.break_state(db, student_id)
    if br is None:
        return None
    return PoolBreakOut(period_id=br.id, since=(br.closed_on or br.opened_on).isoformat(), note=br.note)


@router.get("/pool", response_model=StudentPoolResponse)
def student_pool(user: User = Depends(_require_student), db: Session = Depends(get_db)) -> StudentPoolResponse:
    today = date.today()
    mode = pm.mode_of(user)
    period = pm.get_open_period(db, user.id) if mode == "havuz" else None
    previous = _previous_briefs(db, user.id, period, today) if mode == "havuz" else []
    on_break = _break_out(db, user.id) if mode == "havuz" else None
    if period is None:
        return StudentPoolResponse(mode=mode, today=today.isoformat(), previous=previous, on_break=on_break)
    live = [it for it in period.items if it.removed_at is None and it.approval != APPROVAL_REJECTED]
    for it in live:
        pm.sync_item_progress(db, it)
    db.commit()

    def pull(model, ids):
        ids = {i for i in ids if i}
        return {r.id: r for r in db.query(model).filter(model.id.in_(ids)).all()} if ids else {}
    names = {
        "subjects": pull(Subject, [i.subject_id for i in live]),
        "topics": pull(Topic, [i.topic_id for i in live]),
        "books": pull(Book, [i.book_id for i in live]),
        "sections": pull(BookSection, [i.book_section_id for i in live]),
    }
    cup_tasks = (db.query(Task).filter(Task.student_id == user.id, Task.date == today,
                                       Task.pool_item_id.isnot(None)).order_by(Task.order).all())
    cup_by_item = {t.pool_item_id: t for t in cup_tasks}
    coach = db.get(User, user.teacher_id) if user.teacher_id else None
    cg = pm.class_group_of(db, student=user, coach=coach) if coach else None
    suggested = {it.id for it in pm.cup_suggestions(db, period=period, cg=cg, day=today, limit=3)}
    taught_ids = set(pm.subjects_taught_on(cg, today))
    lesson_today = [s.name for s in db.query(Subject).filter(Subject.id.in_(taught_ids)).all()] if taught_ids else []

    items = []
    for it in live:
        subj = names["subjects"].get(it.subject_id)
        t = cup_by_item.get(it.id)
        items.append(StudentPoolItemOut(
            id=it.id, subject_id=it.subject_id, subject_name=subj.name if subj else "—",
            title=_title(it, names), book_name=names["books"].get(it.book_id).name if it.book_id in names["books"] else None,
            quantity=it.quantity, unit=it.unit, done=it.done_units, remaining=it.remaining,
            day_hint=it.day_hint.isoformat() if it.day_hint else None, source=it.source,
            teacher_homework=bool(it.teacher_homework), approval=it.approval, counts=it.counts_toward_pool,
            in_cup_today=t is not None and t.status != TaskStatus.COMPLETED, cup_task_id=t.id if t else None,
            suggested=it.id in suggested and it.remaining > 0 and t is None,
        ))
    cup = []
    for t in cup_tasks:
        planned = sum(int(bi.planned_count or 0) for bi in t.book_items)
        done = sum(int(bi.completed_count or 0) for bi in t.book_items)
        it_ = next((x for x in live if x.id == t.pool_item_id), None)
        sname = names["subjects"].get(it_.subject_id).name if it_ is not None and it_.subject_id in names["subjects"] else None
        cup.append(StudentCupTask(task_id=t.id, item_id=t.pool_item_id, subject_name=sname, title=t.title, status=t.status.value,
                                  planned=planned, completed=done,
                                  can_return=(t.status != TaskStatus.COMPLETED and done == 0)))
    s = pm.period_summary(db, period, today)
    pace, note = _pace(s, pm.days_without_session(period, today))
    # Haftaya dağılım önerisi — şube ders programına göre (koç önizlemesiyle aynı kural); program yoksa eşit
    lesson_days = cg.lessons if cg is not None else {}
    dist = pm.preview_distribution(live, start=today, days=max(1, s.days_left), lesson_days=lesson_days)
    sname_by_id = {sid: sub.name for sid, sub in names["subjects"].items()}
    lesson_ids = {i for v in lesson_days.values() for i in v}
    lesson_names = ({x.id: x.name for x in db.query(Subject).filter(Subject.id.in_(lesson_ids)).all()}
                    if lesson_ids else {})
    projection = [StudentPoolProjectionDay(
        date=d["date"].isoformat(), units=d["total"],
        lessons=[lesson_names[i] for i in d["lessons"] if i in lesson_names],
        subjects=[StudentPoolProjectionSubject(subject_id=sid, name=sname_by_id.get(sid, "—"), units=u)
                  for sid, u in sorted(d["by_subject"].items(), key=lambda x: -x[1])])
        for d in dist]
    # kendi kalemini eklerken seçebileceği dersler (rehberin gördüğü liste, alan kilidi dahil)
    from app.routes.api_v2.pool import _AYT, _subjects_for
    subs = []
    if coach is not None:
        needs = bool(getattr(user, "is_graduate", False)) or (user.grade_level or 0) >= 11
        locked = needs and user.track is None
        for sub in _subjects_for(db, user, coach.id):
            if locked and sub.exam_section in _AYT and sub.curriculum_model is None:
                continue
            subs.append(StudentPoolSubject(
                id=sub.id, name=sub.name,
                group="sinav" if (sub.exam_section is not None and sub.curriculum_model is None) else "okul",
                is_ayt=sub.exam_section in _AYT and sub.curriculum_model is None))
    # K41/K46/K48: yönlendirme cümleleri — kırmızı/yargı yok
    from app.services import pool_flags as pf
    hints = [StudentPoolHint(**h) for h in pf.student_hints(pf.evaluate_pool_flags(db, user, today))]
    return StudentPoolResponse(
        mode=mode, period_id=period.id, opened_on=period.opened_on.isoformat(),
        summary=StudentPoolSummary(pct=s.pct, total_units=s.total_units, done_units=s.done_units,
                                   items_total=s.items_total, items_done=s.items_done, days_left=s.days_left,
                                   per_day_needed=s.per_day_needed,
                                   expected_next_on=s.expected_next_on.isoformat() if s.expected_next_on else None,
                                   pace=pace, pace_note=note),
        items=items, cup=cup, projection=projection, lesson_today=lesson_today, subjects=subs,
        hints=hints, previous=previous, on_break=on_break, units=list(POOL_UNITS), today=today.isoformat(),
        lesson_days_set=any(v for v in lesson_days.values()),
    )


def _open_or_404(db: Session, user: User):
    if not pm.is_havuz(user):
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "not_havuz",
                                                     "message": "Haftalık havuz modu kapalı."})
    p = pm.get_open_period(db, user.id)
    if p is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "no_open_period",
                                                     "message": "Açık dönem yok; rehberin seansta havuzu yazacak."})
    return p


def _item_or_404(db: Session, user: User, item_id: int, period) -> PoolItem:
    it = db.get(PoolItem, item_id)
    if it is None or it.student_id != user.id or it.period_id != period.id or it.removed_at is not None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "item_not_found",
                                                     "message": "Kalem bulunamadı."})
    return it


@router.post("/pool/cup", response_model=MutationResponse[StudentPoolResponse])
def cup_add(body: StudentCupBody, user: User = Depends(_require_student), db: Session = Depends(get_db)):
    """K34: kalemi (ya da bir kısmını) bugünün kabına al → bugüne görev (rezerv yok)."""
    period = _open_or_404(db, user)
    it = _item_or_404(db, user, body.item_id, period)
    today = date.today()
    try:
        pm.put_in_cup(db, item=it, day=today, count=body.count)
    except PoolError as e:
        raise _http(e, 409 if e.code in ("already_in_cup", "item_done") else 422)
    db.commit()
    return MutationResponse(data=student_pool(user, db), invalidate=_day_keys(user.id, today))


@router.post("/pool/cup/{task_id}/return", response_model=MutationResponse[StudentPoolResponse])
def cup_return(task_id: int, user: User = Depends(_require_student), db: Session = Depends(get_db)):
    """Kaptan havuza geri al — yalnız hiç ilerleme yoksa (işaretlediysen gün sonu kalan döner)."""
    _open_or_404(db, user)
    t = db.get(Task, task_id)
    if t is None or t.student_id != user.id or t.pool_item_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "task_not_found",
                                                     "message": "Kap görevi bulunamadı."})
    done = sum(int(bi.completed_count or 0) for bi in t.book_items)
    if t.status == TaskStatus.COMPLETED or done > 0:
        raise HTTPException(status_code=409, detail={"error": "conflict", "code": "has_progress",
                                                     "message": "Bu kalemde işaretlediğin kısım var; kalan gün sonunda havuza döner."})
    day = t.date
    item = db.get(PoolItem, t.pool_item_id)
    db.delete(t)
    db.flush()
    if item is not None:
        pm.sync_item_progress(db, item)
    db.commit()
    return MutationResponse(data=student_pool(user, db), invalidate=_day_keys(user.id, day))


@router.post("/pool/cup/{task_id}/resize", response_model=MutationResponse[StudentPoolResponse])
def cup_resize(task_id: int, body: StudentCupResizeBody, user: User = Depends(_require_student),
               db: Session = Depends(get_db)):
    """Bugünkü kap görevinin sayısını öğrenci kendisi düzeltir (5 aldı, 3 yapacak). Rehbere talep DEĞİL."""
    _open_or_404(db, user)
    t = db.get(Task, task_id)
    if t is None or t.student_id != user.id or t.pool_item_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "task_not_found",
                                                     "message": "Kap görevi bulunamadı."})
    try:
        pm.resize_cup(db, task=t, count=body.count)
    except PoolError as e:
        raise _http(e, 409 if e.code in ("below_done", "period_closed") else 422)
    db.commit()
    return MutationResponse(data=student_pool(user, db), invalidate=_day_keys(user.id, t.date))


@router.post("/pool/items", response_model=MutationResponse[StudentPoolResponse])
def student_add_item(body: StudentPoolItemBody, user: User = Depends(_require_student),
                     db: Session = Depends(get_db)):
    """K38: öğrenci havuza kalem ekler (öğretmen ödevi, kendi ek çalışması); rehber seansta onaylar."""
    period = _open_or_404(db, user)
    subject = db.get(Subject, body.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "subject_not_found",
                                                     "message": "Ders bulunamadı."})
    topic = db.get(Topic, body.topic_id) if body.topic_id else None
    if body.topic_id and topic is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "topic_not_found",
                                                     "message": "Konu bulunamadı."})
    try:
        pm.add_item(db, period=period, student=user, subject=subject, quantity=body.quantity, unit=body.unit,
                    topic=topic, label=body.label, source=SOURCE_STUDENT, created_by=user,
                    teacher_homework=body.teacher_homework)
    except PoolError as e:
        raise _http(e)
    db.commit()
    return MutationResponse(data=student_pool(user, db),
                            invalidate=[_key(user.id), f"teacher:{user.teacher_id}:students:{user.id}:pool"])


@router.post("/pool/close-day", response_model=MutationResponse[StudentPoolResponse])
def close_day(body: StudentCloseDayBody, user: User = Depends(_require_student), db: Session = Depends(get_db)):
    """K34: günü kapat — kaptaki yapılmayan kısım havuza döner (gece cron da yapar)."""
    _open_or_404(db, user)
    day = _parse_iso_date(body.date) if body.date else date.today()
    if day > date.today():
        raise HTTPException(status_code=422, detail={"error": "validation", "code": "future_day",
                                                     "message": "Gelecek gün kapatılamaz."})
    pm.close_day(db, student=user, day=day)
    db.commit()
    return MutationResponse(data=student_pool(user, db), invalidate=_day_keys(user.id, day))


# ---------------------------------------------------------------- dönem penceresi (geçmiş dönem içi, 2026-10-13)
# Rehber / öğrenci / veli üç uç AYNI üreticiyi kullanır; yüzey farkı `audience` ile:
#   teacher → kaldırılan kalemler (iz) + kaba-girip-döndü sayaçları + onay bekleyen/red kalemler
#   student → kaldırılanlar ve kaçınma sayaçları YOK (K41 yargılamaz); kendi bekleyen kalemi görünür
#   parent  → ek olarak onay bekleyen/red kalemler de YOK (K52 yalnız onaylı havuz)

from app.models.pool import APPROVAL_PENDING, PERIOD_STATUS_LABELS, UNIT_ETKINLIK  # noqa: E402
from app.routes.api_v2.schemas.pool import (  # noqa: E402
    PoolHistoryRow, PoolHistorySubject, PoolPeriodDay, PoolPeriodDayTask, PoolPeriodDetailItem,
    PoolPeriodDetailResponse,
)


def _iso(d) -> str | None:
    return d.isoformat() if d else None


def history_row_out(r: dict) -> PoolHistoryRow:
    return PoolHistoryRow(
        id=r["id"], opened_on=r["opened_on"].isoformat(), closed_on=_iso(r["closed_on"]),
        expected_next_on=_iso(r["expected_next_on"]), status=r["status"],
        status_label=PERIOD_STATUS_LABELS.get(r["status"], r["status"]), note=r["note"],
        total_units=r["total_units"], done_units=r["done_units"], pct=r["pct"], items_total=r["items_total"],
        items_done=r["items_done"], session_marked_units=r["session_marked_units"], carried_in=r["carried_in"],
        carried_out=r["carried_out"], has_session=r["has_session"],
        parent_summary_sent_at=_iso(r["parent_summary_sent_at"]),
        subjects=[PoolHistorySubject(**s) for s in r["subjects"]],
    )


def _sum_opt(vals: list[int | None]) -> int | None:
    present = [int(v) for v in vals if v is not None]
    return sum(present) if present else None


def _day_task_out(t: Task) -> PoolPeriodDayTask:
    bis = list(t.book_items or [])
    itemless = not bis
    planned = sum(int(b.planned_count or 0) for b in bis) if bis else None
    if bis:
        done = sum(int(b.completed_count or 0) for b in bis)
    else:
        done = 1 if t.status == TaskStatus.COMPLETED else 0
    return PoolPeriodDayTask(
        task_id=t.id, item_id=t.pool_item_id, title=t.title, status=t.status.value,
        type=t.type.value if hasattr(t.type, "value") else str(t.type),
        planned=planned, done=done,
        correct=_sum_opt([b.correct_count for b in bis]), wrong=_sum_opt([b.wrong_count for b in bis]),
        blank=_sum_opt([b.blank_count for b in bis]), period=t.period, itemless=itemless,
    )


def period_detail_response(db: Session, period, *, audience: str, today: date | None = None) -> PoolPeriodDetailResponse:
    today = today or date.today()
    det = pm.period_detail(db, period, today=today)
    items = det.items

    def pull(model, ids):
        ids = {i for i in ids if i}
        return {r.id: r for r in db.query(model).filter(model.id.in_(ids)).all()} if ids else {}
    names = {"subjects": pull(Subject, [i.subject_id for i in items]), "topics": pull(Topic, [i.topic_id for i in items]),
             "books": pull(Book, [i.book_id for i in items]), "sections": pull(BookSection, [i.book_section_id for i in items]),
             "users": pull(User, [i.created_by_id for i in items])}

    def out(it: PoolItem) -> PoolPeriodDetailItem:
        subj = names["subjects"].get(it.subject_id)
        top = names["topics"].get(it.topic_id) if it.topic_id else None
        book = names["books"].get(it.book_id) if it.book_id else None
        sec = names["sections"].get(it.book_section_id) if it.book_section_id else None
        creator = names["users"].get(it.created_by_id) if it.created_by_id else None
        coach_view = audience == "teacher"
        return PoolPeriodDetailItem(
            id=it.id, subject_id=it.subject_id, subject_name=subj.name if subj else "—", title=_title(it, names),
            topic_name=top.name if top else None, book_name=book.name if book else None,
            section_label=sec.label if sec else None, label=it.label, quantity=it.quantity, unit=it.unit,
            completed=int(it.completed or 0), session_marked=int(it.session_marked or 0),
            done=it.done_units, remaining=it.remaining, source=it.source,
            teacher_homework=bool(it.teacher_homework), approval=it.approval, counts=it.counts_toward_pool,
            carry_count=int(it.carry_count or 0),
            cup_attempts=int(it.cup_attempts or 0) if coach_view else 0,
            cup_returns=int(det.returns.get(it.id, 0)) if coach_view else 0,
            carried_out=it.id in det.carried_to, exam_linked=it.exam_result_id is not None,
            day_hint=_iso(it.day_hint), removed=it.removed_at is not None, removed_at=_iso(it.removed_at),
            created_by_name=creator.full_name if creator else None,
        )

    live_items: list[PoolPeriodDetailItem] = []
    removed_items: list[PoolPeriodDetailItem] = []
    for it in items:
        if it.removed_at is not None:
            if audience == "teacher":
                removed_items.append(out(it))
            continue
        if audience == "parent" and it.approval in (APPROVAL_PENDING, APPROVAL_REJECTED):
            continue
        if audience == "student" and it.approval == APPROVAL_REJECTED:
            continue
        live_items.append(out(it))
    visible_ids = {o.id for o in live_items}
    days: list[PoolPeriodDay] = []
    for d, tasks in det.days:
        rows = [_day_task_out(t) for t in tasks if t.pool_item_id in visible_ids]
        # birim: test kaleminde çözülen test; etkinlikte görev başına 1 (K42)
        units = 0
        for t, r in zip([t for t in tasks if t.pool_item_id in visible_ids], rows):
            it = next((i for i in items if i.id == t.pool_item_id), None)
            units += 1 if (it is not None and it.unit == UNIT_ETKINLIK and r.done > 0) else r.done
        days.append(PoolPeriodDay(date=d.isoformat(), weekday=d.weekday(), tasks=rows, done_units=units))
    return PoolPeriodDetailResponse(period=history_row_out(det.row), items=live_items, removed_items=removed_items,
                                    days=days, audience=audience, today=today.isoformat())


@router.get("/pool/periods/{period_id}", response_model=PoolPeriodDetailResponse)
def student_pool_period(period_id: int, user: User = Depends(_require_student),
                        db: Session = Depends(get_db)) -> PoolPeriodDetailResponse:
    """Öğrenci kendi geçmiş (ya da açık) dönemini kalem kalem + gün gün görür (K41/K60)."""
    from app.models import StudyPeriod
    period = db.get(StudyPeriod, period_id)
    if period is None or period.student_id != user.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "period_not_found",
                                                     "message": "Dönem bulunamadı."})
    return period_detail_response(db, period, audience="student")
