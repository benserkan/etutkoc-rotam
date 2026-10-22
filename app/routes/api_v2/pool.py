"""Haftalık görev havuzu — REHBER uçları (2026-10-12, Adım 2; tasarım K24–K33).

Tüm yazma kuralları `app/services/pool_mode.py`'de; burada yalnız sahiplik (404),
şekil ve bayatlatma. Gün-gün program uçlarına (teacher.py görev oluşturma) DOKUNMAZ.
Anahtar: teacher:{tid}:students:{sid}:pool
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import (
    Book, BookSection, ClassGroup, PoolItem, StudentBook, StudyPeriod, Subject, Task, TaskBookItem,
    Topic, User,
)
from app.models.curriculum import ExamSection
from app.models.pool import (
    APPROVAL_PENDING, PERIOD_CLOSED, PERIOD_STATUS_LABELS, POOL_UNITS, PROGRAM_MODE_HAVUZ,
)
from app.models.user import TRACK_LABELS
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.pool import (
    ClassPositionBody, LessonDaysBody, ParseBody, ParseChip, ParseResponse, PeriodCloseBody,
    PeriodOpenBody, PoolApproveBody, PoolBundleResponse, PoolQuantityBody, PoolClassGroupOut, PoolItemBody,
    PoolItemOut, PoolPeriodBrief, PoolPeriodOut, PoolStudentOut, PoolSubjectOut, PoolSummaryOut,
    PoolTopicOut, PoolTopicSource, PoolTopicsResponse, PoolVolumeHint, ProgramModeBody,
)
from app.routes.api_v2.teacher import _get_owned_student, _parse_iso_date, _require_teacher
from app.services import pool_mode as pm
from app.services.pool_mode import PoolError

router = APIRouter(prefix="/teacher", tags=["v2-pool"])

_AYT = {ExamSection.AYT_SAY, ExamSection.AYT_EA, ExamSection.AYT_SOZ, ExamSection.AYT_DIL}


def _key(tid: int, sid: int) -> str:
    return f"teacher:{tid}:students:{sid}:pool"


def _keys(tid: int, sid: int) -> list[str]:
    """Havuz değişikliği müfredatı da etkiler (konu 'planlandı'/'devam', seans işareti) — 2026-10-14."""
    return [_key(tid, sid), f"teacher:{tid}:students:{sid}:curriculum",
            f"teacher:{tid}:students:{sid}:topic-board"]


def _http(e: PoolError, status: int = 422) -> HTTPException:
    kind = {404: "not_found", 409: "conflict"}.get(status, "validation")
    return HTTPException(status_code=status, detail={"error": kind, "code": e.code, "message": e.message})


def _iso(d: date | datetime | None) -> str | None:
    return d.isoformat() if d else None


# ---------------------------------------------------------------- serializers

def _item_out(db: Session, it: PoolItem, names: dict) -> PoolItemOut:
    subj = names["subjects"].get(it.subject_id)
    top = names["topics"].get(it.topic_id) if it.topic_id else None
    book = names["books"].get(it.book_id) if it.book_id else None
    sec = names["sections"].get(it.book_section_id) if it.book_section_id else None
    creator = names["users"].get(it.created_by_id) if it.created_by_id else None
    return PoolItemOut(
        id=it.id, subject_id=it.subject_id,
        subject_name=subj.name if subj else ("Genel deneme" if it.exam_kind == "genel" else "—"),
        topic_id=it.topic_id, topic_name=top.name if top else None,
        book_id=it.book_id, book_name=book.name if book else None,
        section_id=it.book_section_id, section_label=sec.label if sec else None,
        label=it.label, quantity=it.quantity, unit=it.unit, completed=it.completed,
        remaining=it.remaining, day_hint=_iso(it.day_hint), source=it.source,
        page_from=it.page_from, page_to=it.page_to,
        teacher_homework=bool(it.teacher_homework), approval=it.approval,
        carry_count=it.carry_count or 0, cup_attempts=it.cup_attempts or 0,
        counts=it.counts_toward_pool,
        created_by_name=creator.full_name if creator else None,
        created_at=_iso(it.created_at),
        book_completed=(names.get("progress", {}).get((it.student_id, it.book_section_id), 0)
                        if it.book_section_id else None),
        book_total=(int(sec.test_count or 0) if sec else None),
        exam_kind=it.exam_kind, exam_section=it.exam_section, question_count=it.question_count,
    )


def _carry_title(o) -> str:
    if o.section_label and o.book_name:
        return f"{o.book_name} — {o.section_label}"
    if o.topic_name:
        return o.topic_name + (f" ({o.book_name})" if o.book_name else "")
    return o.label or o.unit


def _names_for(db: Session, items: list[PoolItem]) -> dict:
    def pull(model, ids):
        ids = {i for i in ids if i}
        return {r.id: r for r in db.query(model).filter(model.id.in_(ids)).all()} if ids else {}
    return {
        "subjects": pull(Subject, [i.subject_id for i in items]),
        "topics": pull(Topic, [i.topic_id for i in items]),
        "books": pull(Book, [i.book_id for i in items]),
        "sections": pull(BookSection, [i.book_section_id for i in items]),
        "users": pull(User, [i.created_by_id for i in items]),
        "progress": _section_progress(db, items),
    }


def _section_progress(db: Session, items: list[PoolItem]) -> dict[tuple[int, int], int]:
    """(öğrenci, bölüm) → kitap sayacında çözülen (kitaplı kalemin ilerleme takibi)."""
    from app.models import SectionProgress
    pairs = {(i.student_id, i.book_section_id) for i in items if i.book_section_id}
    if not pairs:
        return {}
    sids = {p[0] for p in pairs}
    secs = {p[1] for p in pairs}
    rows = (db.query(StudentBook.student_id, SectionProgress.book_section_id, SectionProgress.completed_count)
            .join(SectionProgress, SectionProgress.student_book_id == StudentBook.id)
            .filter(StudentBook.student_id.in_(sids), SectionProgress.book_section_id.in_(secs)).all())
    return {(int(a), int(b)): int(c or 0) for a, b, c in rows}


def _summary_out(s: pm.PeriodSummary) -> PoolSummaryOut:
    return PoolSummaryOut(
        total_units=s.total_units, done_units=s.done_units, pct=s.pct, items_total=s.items_total,
        items_done=s.items_done, pending_student_items=s.pending_student_items,
        days_left=s.days_left, per_day_needed=s.per_day_needed,
        expected_next_on=_iso(s.expected_next_on),
    )


def _period_out(db: Session, p: StudyPeriod, today: date) -> PoolPeriodOut:
    live = [it for it in p.items if it.removed_at is None]
    for it in live:
        pm.sync_item_progress(db, it)
    names = _names_for(db, live)
    return PoolPeriodOut(
        id=p.id, opened_on=p.opened_on.isoformat(), expected_next_on=_iso(p.expected_next_on),
        closed_on=_iso(p.closed_on), status=p.status,
        status_label=PERIOD_STATUS_LABELS.get(p.status, p.status),
        days_open=pm.days_without_session(p, today), note=p.note,
        summary=_summary_out(pm.period_summary(db, p, today)),
        items=[_item_out(db, it, names) for it in live],
    )


def _is_exam(s: Subject) -> bool:
    return s.exam_section is not None and s.curriculum_model is None


def _subjects_for(db: Session, student: User, coach_id: int, *, with_exam: bool = True) -> list[Subject]:
    """Havuzda kalem eklenebilen dersler.

    Omurga = öğrencinin müfredat dersleri (`_applicable_subjects`: 9-10 + Maarif 11 → okul/Maarif;
    Klasik 11-12 + mezun → TYT/AYT) ∪ atanmış kitapların dersleri. 11+ ve mezunda dershane YKS'ye de
    hazırlar → `with_exam` ile alana uygun TYT/AYT dersleri AYRI grup olarak eklenir (Maarif 11'de
    okul Fizik + TYT/AYT Fizik yan yana, etiketli; 2026-10-13 #415). K24 eksik ders şeridi yalnız
    omurgaya bakar (`with_exam=False`)."""
    from app.services.curriculum_progress import _applicable_subjects
    from app.services.curriculum_progress import exam_subject_visible_for_track
    subs = {s.id: s for s in _applicable_subjects(db, student, coach_id)}
    book_subs = (db.query(Subject).join(Book, Book.subject_id == Subject.id)
                 .join(StudentBook, StudentBook.book_id == Book.id)
                 .filter(StudentBook.student_id == student.id, StudentBook.archived_at.is_(None)).all())
    if _klasik_exam_scheme(student):
        # Klasik 11-12 / mezun: görev TYT/AYT'den verilir — sınav karşılığı olmayan okul dersi (İnkılap,
        # İngilizce…) kitap yoksa havuzda anlamsız (kullanıcı 2026-10-13). Dil alanında İngilizce kalır
        # (sistemde ayrı YDT dersi yok).
        from app.models import Track
        subs = {k: s for k, s in subs.items()
                if _is_exam(s) or (student.track == Track.DIL and "ngilizce" in s.name)}
    for s in book_subs:
        subs.setdefault(s.id, s)
    if with_exam and not _maarif_exam_scheme(student) and (bool(student.is_graduate) or (student.grade_level or 0) >= 11):
        for s in (db.query(Subject)
                  .filter(Subject.curriculum_model.is_(None), Subject.exam_section.isnot(None),
                          (Subject.is_builtin.is_(True)) | (Subject.teacher_id == coach_id))
                  .all()):
            if s.covers_grade(student.grade_level, is_graduate=student.is_graduate)                     and exam_subject_visible_for_track(s, student.track):
                subs.setdefault(s.id, s)
    # okul dersleri önce, sınav dersleri sonra (grup başlığıyla gösterilir)
    return sorted(subs.values(), key=lambda s: (1 if _is_exam(s) else 0, (s.order or 0), s.name))


def _maarif_exam_scheme(student: User) -> bool:
    """Maarif modelindeki 11+ öğrenci (mezun hariç) eski (klasik) TYT/AYT taksonomisini GÖRMEZ.

    Kullanıcı kararı 2026-10-13 (#415): Maarif'te sınav sistemi değişmiyor, ama konuları Maarif
    müfredatından — TYT ≈ 9-10. sınıf Maarif konuları ("TYT (Maarif)" grubu), AYT ≈ 11-12. sınıf
    Maarif konuları = zaten öğrencinin kendi sınıf müfredatı (11'de ayrı grup anlamsız; 12. sınıf
    Maarif'e geçince "AYT (Maarif)" anlam kazanır). Eski TYT/AYT dersi yalnız öğrencinin o derste
    KİTABI varsa listede kalır (kitap derse bağlı)."""
    from app.models.curriculum import CurriculumModel
    return (not bool(student.is_graduate) and (student.grade_level or 0) >= 11
            and student.effective_curriculum_model == CurriculumModel.MAARIF_LISE)


def _klasik_exam_scheme(student: User) -> bool:
    """Klasik 11-12 + mezun: sınav omurgası (TYT/AYT) — okul dersi yalnız kitabı varsa listelenir."""
    return ((bool(student.is_graduate) or (student.grade_level or 0) >= 11)
            and not _maarif_exam_scheme(student))


TYT_MAARIF_MAX_GRADE = 10


def _tyt_maarif_ids(db: Session, student: User, subjects: list[Subject]) -> list[int]:
    """Maarif okul derslerinden TYT karşılığı olanlar (İngilizce gibi TYT'de olmayanlar hariç)."""
    if not _maarif_exam_scheme(student):
        return []
    from app.services.curriculum_progress import _SCHOOL_EXAM_SYNONYMS, _exam_base_name
    tyt_bases = {_exam_base_name(n) for (n,) in db.query(Subject.name).filter(
        Subject.curriculum_model.is_(None), Subject.exam_section == ExamSection.TYT).all()}
    out = []
    for s in subjects:
        if _is_exam(s):
            continue
        bases = {s.name} | _SCHOOL_EXAM_SYNONYMS.get(s.name, set())
        if bases & tyt_bases and s.covers_grade(TYT_MAARIF_MAX_GRADE, is_graduate=False):
            out.append(s.id)
    return out


def _curriculum_label(student: User) -> str | None:
    """Okul grubunun başlığı: "Maarif · 11. sınıf" (model + sınıf)."""
    from app.models.curriculum import CurriculumModel
    cm = student.effective_curriculum_model
    names = {CurriculumModel.MAARIF_LISE: "Maarif", CurriculumModel.KLASIK_LISE: "Klasik",
             CurriculumModel.LGS: "LGS"}
    if cm is None:
        return None
    grade = "mezun" if student.is_graduate else (f"{student.grade_level}. sınıf" if student.grade_level else "")
    return f"{names.get(cm, str(cm))} müfredatı" + (f" · {grade}" if grade else "")


def _needs_track(student: User) -> bool:
    return bool(getattr(student, "is_graduate", False)) or (student.grade_level or 0) >= 11


def _class_group_out(db: Session, cg: ClassGroup | None) -> PoolClassGroupOut | None:
    if cg is None:
        return None
    pos = cg.positions
    tids = {int(v.get("topic_id")) for v in pos.values() if v.get("topic_id")}
    tnames = {t.id: t.name for t in db.query(Topic).filter(Topic.id.in_(tids)).all()} if tids else {}
    out = {k: {**v, "topic_name": tnames.get(int(v.get("topic_id") or 0))} for k, v in pos.items()}
    return PoolClassGroupOut(id=cg.id, name=cg.name, positions=out, lesson_days=cg.lessons)


# ---------------------------------------------------------------- GET bundle

@router.get("/students/{student_id}/pool", response_model=PoolBundleResponse)
def get_pool(student_id: int, user: User = Depends(_require_teacher),
             db: Session = Depends(get_db)) -> PoolBundleResponse:
    student = _get_owned_student(db, student_id, user.id)
    today = date.today()
    period = pm.get_open_period(db, student.id)
    all_subs = _subjects_for(db, student, user.id)
    needs = _needs_track(student)
    ayt_locked = needs and student.track is None
    locked_names: list[str] = []
    subjects: list[Subject] = []
    for s in all_subs:
        if s.exam_section in _AYT and s.curriculum_model is None and ayt_locked:
            locked_names.append(s.name)
            continue
        subjects.append(s)
    ayt_locked = ayt_locked and bool(locked_names)  # kilitlenecek AYT dersi yoksa (Maarif 11) not gösterilmez
    from app.services.gorev_stats import DENEME_BOOK_TYPES
    book_n: dict[int, int] = {}
    deneme_n: dict[int, int] = {}
    for subj_id, btype in (db.query(Book.subject_id, Book.type).join(StudentBook, StudentBook.book_id == Book.id)
                           .filter(StudentBook.student_id == student.id, StudentBook.archived_at.is_(None)).all()):
        bucket = deneme_n if btype in DENEME_BOOK_TYPES else book_n
        bucket[subj_id] = bucket.get(subj_id, 0) + 1
    counts: dict[int, int] = {}
    if period is not None:
        for it in period.items:
            if it.removed_at is None and it.subject_id:
                counts[it.subject_id] = counts.get(it.subject_id, 0) + 1
    backbone = {s.id for s in _subjects_for(db, student, user.id, with_exam=False)}
    missing = ([s.name for s in subjects if s.id in backbone and counts.get(s.id, 0) == 0]
               if period is not None else [])

    periods = pm.list_periods(db, student.id, limit=8)
    briefs: list[PoolPeriodBrief] = []
    done_hist: list[int] = []
    for p in periods:
        s = pm.period_summary(db, p, today)
        briefs.append(PoolPeriodBrief(
            id=p.id, opened_on=p.opened_on.isoformat(), closed_on=_iso(p.closed_on), status=p.status,
            status_label=PERIOD_STATUS_LABELS.get(p.status, p.status),
            total_units=s.total_units, done_units=s.done_units, pct=s.pct,
            parent_summary_sent_at=p.parent_summary_sent_at.isoformat() if p.parent_summary_sent_at else None))
        if p.status == PERIOD_CLOSED and len(done_hist) < 3:
            done_hist.append(s.done_units)
    vol = PoolVolumeHint(
        avg_done_last3=int(round(sum(done_hist) / len(done_hist))) if done_hist else None,
        current_total=pm.period_summary(db, period, today).total_units if period else 0,
    )
    cg = pm.class_group_of(db, student=student, coach=user)
    # Adım 6: dönem açarken devir adayları (son kapanmış dönem) + ara durumu + toplam dönem
    carry_out: list = []
    carry_src = None
    on_break = None
    if period is None:
        from app.routes.api_v2.schemas.pool import PoolBreakOut, PoolCarryCandidate
        src, cands = pm.carry_candidates(db, student.id)
        if src is not None and cands:
            carry_src = src.id
            cn = _names_for(db, cands)
            for it in cands:
                base_item = _item_out(db, it, cn)
                carry_out.append(PoolCarryCandidate(
                    item_id=it.id, subject_name=base_item.subject_name, title=_carry_title(base_item),
                    unit=it.unit, remaining=it.remaining, quantity=it.quantity, carry_count=int(it.carry_count or 0),
                    third_carry=int(it.carry_count or 0) + 1 >= 3, teacher_homework=bool(it.teacher_homework)))
        br = pm.break_state(db, student.id)
        if br is not None:
            on_break = PoolBreakOut(period_id=br.id, since=(br.closed_on or br.opened_on).isoformat(), note=br.note)
    periods_total = db.query(func.count(StudyPeriod.id)).filter(StudyPeriod.student_id == student.id).scalar() or 0
    db.commit()  # sync_item_progress yazmış olabilir
    return PoolBundleResponse(
        carry_candidates=carry_out, carry_source_period_id=carry_src, on_break=on_break,
        periods_total=int(periods_total),
        student=PoolStudentOut(
            id=student.id, full_name=student.full_name, program_mode=pm.mode_of(student),
            grade_level=student.grade_level, is_graduate=bool(student.is_graduate),
            track=student.track.value if student.track else None,
            track_label=TRACK_LABELS.get(student.track) if student.track else None,
            needs_track=needs, class_group=student.class_group,
        ),
        period=_period_out(db, period, today) if period else None,
        periods=briefs,
        subjects=[PoolSubjectOut(id=s.id, name=s.name,
                                 is_ayt=(s.exam_section in _AYT and s.curriculum_model is None),
                                 item_count=counts.get(s.id, 0),
                                 group="sinav" if _is_exam(s) else "okul",
                                 book_count=book_n.get(s.id, 0), deneme_count=deneme_n.get(s.id, 0)) for s in subjects],
        curriculum_label=_curriculum_label(student),
        tyt_maarif_subject_ids=_tyt_maarif_ids(db, student, subjects),
        tyt_maarif_max_grade=TYT_MAARIF_MAX_GRADE,
        ayt_locked=ayt_locked, locked_ayt_names=locked_names, missing_subjects=missing,
        class_group=_class_group_out(db, cg), volume=vol, flags=_flags_out(db, student, today),
        units=list(POOL_UNITS),
        today=today.isoformat(),
    )


# ---------------------------------------------------------------- konu listesi (K27)

@router.get("/students/{student_id}/pool/topics", response_model=PoolTopicsResponse)
def pool_topics(student_id: int, subject_id: int = Query(...),
                user: User = Depends(_require_teacher), db: Session = Depends(get_db)) -> PoolTopicsResponse:
    from app.services.topic_board import build_topic_board
    student = _get_owned_student(db, student_id, user.id)
    subject = db.get(Subject, subject_id)
    if subject is None or subject.id not in {s.id for s in _subjects_for(db, student, user.id)}:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "subject_not_found",
                                                     "message": "Ders bulunamadı."})
    page = build_topic_board(db, student=student, coach_id=user.id, subject_id=subject.id, allow_subject=subject)
    board = next((s for s in page.subjects if s.subject_id == subject.id), None)

    # SON: konunun en son havuza girdiği gün (kalem) ya da görev aldığı gün
    last: dict[int, date] = {}
    for tid, created in (db.query(PoolItem.topic_id, func.max(PoolItem.created_at))
                         .filter(PoolItem.student_id == student.id, PoolItem.topic_id.isnot(None),
                                 PoolItem.removed_at.is_(None)).group_by(PoolItem.topic_id).all()):
        if created:
            last[int(tid)] = pm.tr_date(created)
    for tid, d in (db.query(BookSection.topic_id, func.max(Task.date))
                   .join(TaskBookItem, TaskBookItem.book_section_id == BookSection.id)
                   .join(Task, Task.id == TaskBookItem.task_id)
                   .filter(Task.student_id == student.id, BookSection.topic_id.isnot(None))
                   .group_by(BookSection.topic_id).all()):
        if d and (tid not in last or d > last[int(tid)]):
            last[int(tid)] = d
    for tid, d in (db.query(TaskBookItem.topic_id, func.max(Task.date))
                   .join(Task, Task.id == TaskBookItem.task_id)
                   .filter(Task.student_id == student.id, TaskBookItem.topic_id.isnot(None))
                   .group_by(TaskBookItem.topic_id).all()):
        if d and (tid not in last or d > last[int(tid)]):
            last[int(tid)] = d
    newest = max(last.values()) if last else None
    cg = pm.class_group_of(db, student=student, coach=user)
    pos_topic = None
    if cg is not None:
        pos_topic = (cg.positions.get(str(subject.id)) or {}).get("topic_id")

    topics: list[PoolTopicOut] = []
    for t in (board.topics if board else []):
        topics.append(PoolTopicOut(
            topic_id=t.topic_id, name=t.name, unit_name=t.unit_name, status=t.status,
            grade_level=getattr(t, "grade_level", None),
            remaining=t.remaining, tests_solved=t.tests_solved, accuracy_pct=t.accuracy_pct,
            last_assigned_on=_iso(last.get(t.topic_id)),
            is_last=bool(newest and last.get(t.topic_id) == newest),
            is_class_position=(pos_topic is not None and int(pos_topic) == t.topic_id),
            sources=[PoolTopicSource(book_id=s.book_id, book_name=s.book_name, section_id=s.section_id,
                                     section_label=s.section_label, total=s.total, remaining=s.remaining,
                                     completed=getattr(s, "completed", 0),
                                     recommended=getattr(s, "recommended", False))
                     for s in t.sources],
        ))
    return PoolTopicsResponse(subject_id=subject.id, subject_name=subject.name, topics=topics)


# ---------------------------------------------------------------- yazma uçları

def _bundle_mut(db: Session, user: User, student: User) -> MutationResponse[PoolBundleResponse]:
    db.commit()
    return MutationResponse(data=get_pool(student.id, user, db), invalidate=[*_keys(user.id, student.id)])


@router.post("/students/{student_id}/program-mode", response_model=MutationResponse[PoolBundleResponse])
def set_mode(student_id: int, body: ProgramModeBody, user: User = Depends(_require_teacher),
             db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    try:
        pm.set_program_mode(db, student, body.mode)
    except PoolError as e:
        raise _http(e, 409)
    db.commit()
    res = get_pool(student.id, user, db)
    # öğrenci detayı / liste de modu gösterir → öğrenci önekini bayatlat
    return MutationResponse(data=res, invalidate=[*_keys(user.id, student.id),
                                                  f"teacher:{user.id}:students:{student.id}"])


# ---------------------------------------------------------------- 2026-10-15 mod geçişi (temizlikli)

from app.routes.api_v2.schemas.pool import (  # noqa: E402
    ModeChangeOut, ModeHistoryResponse, ModeSwitchBody, ModeSwitchPreviewResponse, ModeSwitchTask,
)
from app.services import program_mode_switch as pms  # noqa: E402

_TRIGGER_LABELS = {pms.TRIGGER_MANUAL: "Elle geçiş", pms.TRIGGER_SESSION_FINISH: "Seansı bitirirken"}


def _mode_keys(tid: int, sid: int) -> list[str]:
    # öğrenci öneki hafta/gün/kitap/kapasite/uyarı yüzeylerinin hepsini kapsar
    return [*_keys(tid, sid), f"teacher:{tid}:students:{sid}"]


def _preview_out(pv: "pms.SwitchPreview") -> ModeSwitchPreviewResponse:
    def tb(x):
        return ModeSwitchTask(**x.__dict__)
    return ModeSwitchPreviewResponse(
        from_mode=pv.from_mode, to_mode=pv.to_mode, effective_on=pv.effective_on, allowed=pv.allowed,
        blocker=pv.blocker, blocker_message=pv.blocker_message,
        delete_tasks=[tb(t) for t in pv.delete_tasks], keep_partial=[tb(t) for t in pv.keep_partial],
        release_tests=pv.release_tests, dead_reserve_tests=pv.dead_reserve_tests,
        pool_leftover_items=pv.pool_leftover_items, pool_leftover_units=pv.pool_leftover_units,
        notes=pv.notes)


@router.get("/students/{student_id}/program-mode/preview", response_model=ModeSwitchPreviewResponse)
def mode_switch_preview(student_id: int, to: str = Query(pattern="^(gun_gun|havuz)$"),
                        effective_on: str | None = None, user: User = Depends(_require_teacher),
                        db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    eff = _parse_iso_date(effective_on) if effective_on else pm.tr_date(pm._now())
    return _preview_out(pms.preview(db, student, to, eff))


@router.post("/students/{student_id}/program-mode/switch", response_model=MutationResponse[PoolBundleResponse])
def mode_switch(student_id: int, body: ModeSwitchBody, background_tasks: BackgroundTasks,
                user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Gün gün ↔ havuz geçişi: ileri tarihli dokunulmamış görevler silinir, rezervler iade edilir,
    kısmen çözülmüş görev kalır; geçiş kaydı yazılır. Havuza geçişte isteğe bağlı ilk dönem açılır."""
    student = _get_owned_student(db, student_id, user.id)
    eff = _parse_iso_date(body.effective_on) if body.effective_on else pm.tr_date(pm._now())
    if eff < pm.tr_date(pm._now()):
        raise HTTPException(status_code=422, detail={"error": "validation", "code": "past_effective_on",
                                                     "message": "Geçiş günü bugünden önce olamaz."})
    nxt = _parse_iso_date(body.expected_next_on) if body.expected_next_on else None
    try:
        if body.to_mode == PROGRAM_MODE_HAVUZ:
            pms.switch_to_havuz(db, student=student, actor=user, effective_on=eff,
                                open_first_period=body.open_first_period, expected_next_on=nxt, note=body.note)
        else:
            pms.switch_to_gun_gun(db, student=student, actor=user, effective_on=eff, note=body.note)
    except (pms.SwitchError, PoolError) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail={"error": "conflict", "code": e.code, "message": e.message})
    db.commit()
    from app.services.student_email_fallback import notify_student_program_mode_bg

    background_tasks.add_task(
        notify_student_program_mode_bg, student.id, body.to_mode, eff.isoformat(),
        nxt.isoformat() if (nxt and body.to_mode == PROGRAM_MODE_HAVUZ and body.open_first_period) else None)
    return MutationResponse(data=get_pool(student.id, user, db), invalidate=_mode_keys(user.id, student.id))


@router.get("/students/{student_id}/program-mode/history", response_model=ModeHistoryResponse)
def mode_history(student_id: int, user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    import json as _json
    from app.models.pool import PROGRAM_MODE_LABELS

    student = _get_owned_student(db, student_id, user.id)
    rows = pms.history(db, student.id)
    names = {u.id: u.full_name for u in db.query(User).filter(
        User.id.in_({r.changed_by_id for r in rows if r.changed_by_id})).all()} if rows else {}
    out = []
    for r in rows:
        try:
            summ = _json.loads(r.summary_json) if r.summary_json else {}
        except ValueError:
            summ = {}
        out.append(ModeChangeOut(
            id=r.id, from_mode=r.from_mode, to_mode=r.to_mode,
            from_label=PROGRAM_MODE_LABELS.get(r.from_mode, r.from_mode),
            to_label=PROGRAM_MODE_LABELS.get(r.to_mode, r.to_mode),
            effective_on=r.effective_on.isoformat(), trigger=r.trigger,
            trigger_label=_TRIGGER_LABELS.get(r.trigger, r.trigger),
            changed_by_name=names.get(r.changed_by_id), note=r.note, summary=summ,
            created_at=_iso(r.created_at)))
    return ModeHistoryResponse(current_mode=pm.mode_of(student), items=out)


@router.post("/students/{student_id}/pool/periods", response_model=MutationResponse[PoolBundleResponse])
def open_period(student_id: int, body: PeriodOpenBody, user: User = Depends(_require_teacher),
                db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    opened = _parse_iso_date(body.opened_on)
    nxt = _parse_iso_date(body.expected_next_on) if body.expected_next_on else None
    try:
        pm.open_period(db, student=student, coach=user, opened_on=opened, expected_next_on=nxt,
                       note=body.note, carry=[(c.item_id, c.quantity) for c in body.carry])
    except PoolError as e:
        db.rollback()
        raise _http(e, 409 if e.code == "already_open" else 422)
    return _bundle_mut(db, user, student)


@router.post("/students/{student_id}/pool/periods/{period_id}/close",
             response_model=MutationResponse[PoolBundleResponse])
def close_period(student_id: int, period_id: int, body: PeriodCloseBody,
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    p = db.get(StudyPeriod, period_id)
    if p is None or p.student_id != student.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "period_not_found",
                                                     "message": "Dönem bulunamadı."})
    try:
        pm.close_period(db, p, closed_on=_parse_iso_date(body.closed_on), status=body.status)
    except PoolError as e:
        raise _http(e, 409 if e.code == "not_open" else 422)
    if body.note and body.note.strip():
        p.note = body.note.strip()
    return _bundle_mut(db, user, student)


@router.post("/students/{student_id}/pool/periods/{period_id}/expected",
             response_model=MutationResponse[PoolBundleResponse])
def set_expected(student_id: int, period_id: int, body: PeriodOpenBody,
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """K8: beklenen sonraki seans gününü değiştir (öğrenci gelmedi, başka güne yazıldı)."""
    student = _get_owned_student(db, student_id, user.id)
    p = db.get(StudyPeriod, period_id)
    if p is None or p.student_id != student.id or not p.is_open:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "period_not_found",
                                                     "message": "Açık dönem bulunamadı."})
    nxt = _parse_iso_date(body.expected_next_on) if body.expected_next_on else None
    if nxt is not None and nxt <= p.opened_on:
        raise HTTPException(status_code=422, detail={"error": "validation", "code": "bad_expected",
                                                     "message": "Beklenen gün dönem başlangıcından sonra olmalı."})
    p.expected_next_on = nxt
    if body.note is not None:
        p.note = body.note
    return _bundle_mut(db, user, student)


def _open_or_404(db: Session, student: User) -> StudyPeriod:
    p = pm.get_open_period(db, student.id)
    if p is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "no_open_period",
                                                     "message": "Açık dönem yok; önce dönemi aç."})
    return p


@router.post("/students/{student_id}/pool/items", response_model=MutationResponse[PoolBundleResponse])
def add_item(student_id: int, body: PoolItemBody, user: User = Depends(_require_teacher),
             db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    p = _open_or_404(db, student)
    subject = db.get(Subject, body.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "subject_not_found",
                                                     "message": "Ders bulunamadı."})
    topic = db.get(Topic, body.topic_id) if body.topic_id else None
    book = db.get(Book, body.book_id) if body.book_id else None
    section = db.get(BookSection, body.section_id) if body.section_id else None
    if (body.topic_id and topic is None) or (body.book_id and book is None) or (body.section_id and section is None):
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "ref_not_found",
                                                     "message": "Konu/kitap/bölüm bulunamadı."})
    try:
        pm.add_item(db, period=p, student=student, subject=subject, quantity=body.quantity, unit=body.unit,
                    topic=topic, book=book, section=section, label=body.label,
                    day_hint=_parse_iso_date(body.day_hint) if body.day_hint else None,
                    source=body.source, created_by=user, teacher_homework=body.teacher_homework,
                    exam_result_id=body.exam_result_id,
                    page_from=body.page_from, page_to=body.page_to)
    except PoolError as e:
        raise _http(e)
    return _bundle_mut(db, user, student)


def _item_or_404(db: Session, student: User, item_id: int) -> PoolItem:
    it = db.get(PoolItem, item_id)
    if it is None or it.student_id != student.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "item_not_found",
                                                     "message": "Kalem bulunamadı."})
    return it


@router.post("/students/{student_id}/pool/items/{item_id}/delete",
             response_model=MutationResponse[PoolBundleResponse])
def delete_item(student_id: int, item_id: int, user: User = Depends(_require_teacher),
                db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    pm.remove_item(db, _item_or_404(db, student, item_id), user)
    return _bundle_mut(db, user, student)


@router.post("/students/{student_id}/pool/items/{item_id}/quantity",
             response_model=MutationResponse[PoolBundleResponse])
def set_item_quantity(student_id: int, item_id: int, body: PoolQuantityBody,
                      user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    try:
        pm.set_item_quantity(db, _item_or_404(db, student, item_id), body.quantity, user)
    except PoolError as e:
        raise _http(e)
    return _bundle_mut(db, user, student)


@router.post("/students/{student_id}/pool/items/{item_id}/approve",
             response_model=MutationResponse[PoolBundleResponse])
def approve_item(student_id: int, item_id: int, body: PoolApproveBody,
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    try:
        pm.approve_item(db, _item_or_404(db, student, item_id), user, body.approved)
    except PoolError as e:
        raise _http(e)
    return _bundle_mut(db, user, student)


# ---------------------------------------------------------------- şube (K9 / K37)

@router.post("/students/{student_id}/pool/class-group/position",
             response_model=MutationResponse[PoolBundleResponse])
def set_position(student_id: int, body: ClassPositionBody, user: User = Depends(_require_teacher),
                 db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    if not student.class_group:
        raise HTTPException(status_code=422, detail={"error": "validation", "code": "no_class_group",
                                                     "message": "Öğrencinin şubesi yok; konu konumu şubeye yazılır."})
    if body.topic_id:
        t = db.get(Topic, body.topic_id)
        if t is None or t.subject_id != body.subject_id:
            raise HTTPException(status_code=422, detail={"error": "validation", "code": "topic_subject_mismatch",
                                                         "message": "Konu seçilen derse ait değil."})
    cg = pm.get_or_create_class_group(db, coach=user, name=student.class_group)
    pm.set_topic_position(db, cg, subject_id=body.subject_id, topic_id=body.topic_id, actor=user,
                          on=date.today())
    db.commit()
    # aynı şubedeki tüm öğrencilerin havuz ekranı değişir → şube önekini de bayatlat
    return MutationResponse(data=get_pool(student.id, user, db),
                            invalidate=[*_keys(user.id, student.id), f"teacher:{user.id}:class-group:{cg.id}"])


@router.post("/students/{student_id}/pool/class-group/lesson-days",
             response_model=MutationResponse[PoolBundleResponse])
def set_lessons(student_id: int, body: LessonDaysBody, user: User = Depends(_require_teacher),
                db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    if not student.class_group:
        raise HTTPException(status_code=422, detail={"error": "validation", "code": "no_class_group",
                                                     "message": "Öğrencinin şubesi yok; ders programı şubeye yazılır."})
    try:
        lessons = {int(k): [int(x) for x in v] for k, v in body.lessons.items()}
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail={"error": "validation", "code": "bad_lessons",
                                                     "message": "Ders programı biçimi hatalı."})
    cg = pm.get_or_create_class_group(db, coach=user, name=student.class_group)
    pm.set_lesson_days(db, cg, lessons)
    return _bundle_mut(db, user, student)


# ---------------------------------------------------------------- serbest metin (K28)

@router.post("/students/{student_id}/pool/parse", response_model=ParseResponse)
def parse_text(student_id: int, body: ParseBody, user: User = Depends(_require_teacher),
               db: Session = Depends(get_db)) -> ParseResponse:
    """Serbest metni çiplere ayırır, SESSİZCE yazmaz — rehber onaylar."""
    student = _get_owned_student(db, student_id, user.id)
    subjects = _subjects_for(db, student, user.id)
    res = pm.parse_free_text(db, student=student, subjects=subjects, text=body.text,
                             subject_id=body.subject_id)
    chips = [ParseChip(kind=c["kind"], id=c.get("id"), label=c["label"], confident=c.get("confident", True))
             for c in res["chips"]]
    draft = None
    d = res.get("draft")
    if d:
        draft = PoolItemBody(**d)
    from app.routes.api_v2.schemas.pool import ParseBase, ParseOption
    return ParseResponse(chips=chips, draft=draft, warning=res.get("warning"),
                         options=[ParseOption(**o) for o in res.get("options") or []],
                         base=ParseBase(**res["base"]) if res.get("base") else None)


def _flags_out(db: Session, student: User, today: date):
    """Adım 4: havuz erken uyarı paketi (pool_flags) — bundle + seans ekranı ortak."""
    from app.routes.api_v2.schemas.pool import PoolFlagEvidence, PoolFlagOut, PoolFlagsOut
    from app.services import pool_flags as pf
    rep = pf.evaluate_pool_flags(db, student, today)

    def out(w):
        return PoolFlagOut(code=w.code, level=w.level, layer=getattr(w, "layer", ""), title=w.title,
                           detail=w.detail, coach_only=bool(getattr(w, "coach_only", False)),
                           evidence=[PoolFlagEvidence(label=a, value=b) for a, b in (w.evidence or [])])
    return PoolFlagsOut(headline=rep.headline, level=rep.level,
                        primary=[out(w) for w in rep.primary], secondary=[out(w) for w in rep.secondary],
                        good=[out(w) for w in rep.good],
                        paper_student=any(w.code == "pool_paper" for w in rep.secondary))


# ---------------------------------------------------------------- seans ekranı (K18–K22)

from app.routes.api_v2.schemas.pool import (  # noqa: E402
    PoolSessionResponse, SessionAgendaOut, SessionExamStrip, SessionExamTopic, SessionFinishBody,
    SessionItemOut, SessionMarkBody, SessionPrevious,
)


def _session_item(db: Session, it: PoolItem, names: dict, avoided: dict[int, str],
                  closed: set[int] | frozenset = frozenset()) -> SessionItemOut:
    base_item = _item_out(db, it, names)
    tid = it.topic_id or (it.section.topic_id if it.section is not None else None)
    return SessionItemOut(**base_item.model_dump(), session_marked=int(it.session_marked or 0),
                          done_units=it.done_units, avoided=it.id in avoided, avoided_reason=avoided.get(it.id),
                          closure_topic_id=tid, topic_closed=bool(tid and tid in closed))


def _headline(summary: pm.PeriodSummary, avoided_n: int, pending_n: int) -> str:
    if summary.total_units == 0:
        return "Havuz boştu; bu dönemde kalem yazılmadı."
    parts = [f"Havuz tamamlanma yüzde {summary.pct} ({summary.done_units}/{summary.total_units} birim, "
             f"{summary.items_done}/{summary.items_total} kalem)."]
    if avoided_n:
        parts.append(f"{avoided_n} kalemden kaçınma var.")
    if pending_n:
        parts.append(f"{pending_n} kalemi öğrenci ekledi, onay bekliyor.")
    return " ".join(parts)


@router.get("/students/{student_id}/pool/session", response_model=PoolSessionResponse)
def pool_session(student_id: int, user: User = Depends(_require_teacher),
                 db: Session = Depends(get_db)) -> PoolSessionResponse:
    from app.models import CoachingSession
    from app.services import exam_progress

    student = _get_owned_student(db, student_id, user.id)
    today = date.today()
    period = pm.get_open_period(db, student.id)
    bundle = get_pool(student_id, user, db)  # öğrenci + mod + dönem özeti (sync dahil)
    if period is None:
        return PoolSessionResponse(student=bundle.student, period=None, headline="Açık dönem yok.",
                                   today=today.isoformat())
    live = [it for it in period.items if it.removed_at is None]
    names = _names_for(db, live)
    av = {it.id: reason for it, reason in pm.avoid_reasons(period, today, db).items()}
    from app.services import topic_closure
    closed = topic_closure.closed_topic_ids(db, student.id)
    items = [_session_item(db, it, names, av, closed) for it in live]
    summary = pm.period_summary(db, period, today)
    pending = [i for i in items if i.source == "ogrenci" and i.approval == APPROVAL_PENDING]
    exam = pm.exam_strip(db, student=student, period=period)
    prev = (db.query(CoachingSession).filter(CoachingSession.student_id == student.id)
            .order_by(CoachingSession.session_date.desc(), CoachingSession.id.desc()).first())
    queue = exam_progress.get_queue(db, student.id)
    return PoolSessionResponse(
        student=bundle.student, period=bundle.period,
        headline=_headline(summary, len(av), len(pending)),
        items=items, avoided=[i for i in items if i.avoided], pending_student_items=pending,
        exam=SessionExamStrip(
            **{**exam, "wrong_topics": [SessionExamTopic(**t) for t in exam["wrong_topics"]],
               "studied_but_wrong": [SessionExamTopic(**t) for t in exam["studied_but_wrong"]]},
        ) if exam else None,
        previous_session=SessionPrevious(
            id=prev.id, session_date=prev.session_date.isoformat(), agenda=prev.agenda or "",
            coach_note=prev.coach_note, next_change=prev.next_change, mood=prev.mood) if prev else None,
        agenda_queue=[SessionAgendaOut(id=str(q.get("id")), text=str(q.get("text") or ""),
                                       source=q.get("source")) for q in queue],
        flags=_flags_out(db, student, today),
        today=today.isoformat(),
    )


@router.post("/students/{student_id}/pool/items/{item_id}/session-mark",
             response_model=MutationResponse[PoolSessionResponse])
def session_mark(student_id: int, item_id: int, body: SessionMarkBody,
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """K18: rehber seansta kaynağa bakıp yapılmış birimi yazar (öğrenci kaydından ayrı sayaç)."""
    student = _get_owned_student(db, student_id, user.id)
    it = _item_or_404(db, student, item_id)
    if not it.period.is_open:
        raise HTTPException(status_code=409, detail={"error": "conflict", "code": "period_closed",
                                                     "message": "Dönem kapalı."})
    try:
        pm.session_mark(db, item=it, actor=user, count=body.count, note=body.note)
    except PoolError as e:
        raise _http(e)
    db.commit()
    return MutationResponse(data=pool_session(student.id, user, db),
                            invalidate=[*_keys(user.id, student.id),
                                        f"teacher:{user.id}:students:{student.id}:books"])


@router.post("/students/{student_id}/pool/session/finish",
             response_model=MutationResponse[PoolBundleResponse])
def session_finish(student_id: int, body: SessionFinishBody, background_tasks: BackgroundTasks,
                   user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """K22/K32: seansı bitir → dönem kapanır, seans kaydı, yeni dönem, kalem kalem devir."""
    student = _get_owned_student(db, student_id, user.id)
    period = _open_or_404(db, student)
    closed = _parse_iso_date(body.closed_on)
    nxt = _parse_iso_date(body.expected_next_on) if body.expected_next_on else None
    if body.switch_to_gun_gun:
        from app.services import program_mode_switch as _pms
        if body.carry:
            raise HTTPException(status_code=422, detail={"error": "validation", "code": "carry_with_switch",
                                                         "message": "Gün gün programa geçerken kalem devredilmez."})
        try:
            _pms.finish_session_to_gun_gun(
                db, student=student, coach=user, period=period, closed_on=closed,
                record_session=body.record_session, agenda=body.agenda, coach_note=body.coach_note,
                next_change=body.next_change, mood=body.mood)
        except (_pms.SwitchError, PoolError) as e:
            db.rollback()
            raise _http(e, 409)
        db.commit()
        from app.services.student_email_fallback import notify_student_program_mode_bg

        background_tasks.add_task(notify_student_program_mode_bg, student.id, "gun_gun", closed.isoformat(), None)
        return MutationResponse(data=get_pool(student.id, user, db),
                                invalidate=[*_keys(user.id, student.id),
                                            f"teacher:{user.id}:students:{student.id}"])
    try:
        pm.finish_session(
            db, student=student, coach=user, period=period, closed_on=closed, expected_next_on=nxt,
            carry=[(c.item_id, c.quantity) for c in body.carry], record_session=body.record_session,
            agenda=body.agenda, coach_note=body.coach_note, next_change=body.next_change, mood=body.mood,
            new_period_note=body.new_period_note,
        )
    except PoolError as e:
        db.rollback()
        raise _http(e, 409 if e.code in ("not_open", "already_open") else 422)
    db.commit()
    return MutationResponse(data=get_pool(student.id, user, db),
                            invalidate=[*_keys(user.id, student.id),
                                        f"teacher:{user.id}:students:{student.id}:sessions",
                                        f"teacher:{user.id}:students:{student.id}"])


# ---------------------------------------------------------------- K53 veli seans özeti

from app.routes.api_v2.schemas.pool import (  # noqa: E402
    PoolDailyCounts, PoolDailyResponse, PoolDailyRow, PoolFlagOut as _PFO, PoolFlagEvidence as _PFE,
    PoolParentRecipient, PoolParentSummaryResponse, PoolParentSummarySendBody, PoolParentSummarySendResult,
)


def _period_or_404(db: Session, student: User, period_id: int) -> StudyPeriod:
    p = db.get(StudyPeriod, period_id)
    if p is None or p.student_id != student.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "period_not_found",
                                                     "message": "Dönem bulunamadı."})
    return p


def _recipients_out(db: Session, student: User) -> list[PoolParentRecipient]:
    from app.models import NotificationChannel, NotificationKind
    from app.services import pool_parent_summary as pps
    from app.services.notification_producer import suppression_reason
    out = []
    for parent, link in pps.recipients(db, student.id):
        reason = None
        if link.muted:
            reason = "bu çocuk için bildirimleri sessize almış"
        else:
            r = suppression_reason(db, parent_id=parent.id, student_id=student.id,
                                   kind=NotificationKind.WEEKLY_REPORT, channel=NotificationChannel.EMAIL)
            reason = r if isinstance(r, str) else (None if not r else str(r))
        out.append(PoolParentRecipient(parent_id=parent.id, name=parent.full_name, email=parent.email,
                                       will_send=reason is None, reason=reason))
    return out


def _parent_summary_response(db: Session, student: User, period: StudyPeriod) -> PoolParentSummaryResponse:
    from app.services import pool_parent_summary as pps
    snap = pps.sent_snapshot(period)
    if snap:
        data = {**snap, "is_sent_snapshot": True}
    else:
        data = {**pps.build_summary(db, period), "include_items": True, "include_exam": True, "is_sent_snapshot": False}
    return PoolParentSummaryResponse(
        **{k: v for k, v in data.items() if k in PoolParentSummaryResponse.model_fields},
        recipients=_recipients_out(db, student),
        sent_at=period.parent_summary_sent_at.isoformat() if period.parent_summary_sent_at else None,
    )


@router.get("/students/{student_id}/pool/periods/{period_id}/parent-summary",
            response_model=PoolParentSummaryResponse)
def pool_parent_summary(student_id: int, period_id: int, user: User = Depends(_require_teacher),
                        db: Session = Depends(get_db)) -> PoolParentSummaryResponse:
    """K53: veliye gidecek dönem özeti — ÖNİZLEME (gönderim yok). Gönderildiyse gönderilen hâl."""
    student = _get_owned_student(db, student_id, user.id)
    period = _period_or_404(db, student, period_id)
    return _parent_summary_response(db, student, period)


@router.post("/students/{student_id}/pool/periods/{period_id}/parent-summary/send",
             response_model=MutationResponse[PoolParentSummarySendResult])
def pool_parent_summary_send(student_id: int, period_id: int, body: PoolParentSummarySendBody,
                             user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """K53: rehberin düzenlediği metinle veliye gönder (dönem başına bir kez; otomatik gitmez)."""
    from app.services import pool_parent_summary as pps
    student = _get_owned_student(db, student_id, user.id)
    period = _period_or_404(db, student, period_id)
    if period.is_open:
        raise HTTPException(status_code=409, detail={"error": "conflict", "code": "period_open",
                                                     "message": "Dönem henüz kapanmadı; özet seans bitince gönderilir."})
    if period.parent_summary_sent_at is not None:
        raise HTTPException(status_code=409, detail={"error": "conflict", "code": "already_sent",
                                                     "message": "Bu dönemin özeti zaten gönderildi."})
    if not pps.recipients(db, student.id):
        raise HTTPException(status_code=422, detail={"error": "validation", "code": "no_parent",
                                                     "message": "Bu öğrenciye bağlı veli yok."})
    try:
        res = pps.send_summary(db, period=period, actor=user, narrative=pps.clean_narrative(body.narrative),
                               include_items=body.include_items, include_exam=body.include_exam)
    except Exception as e:  # noqa: BLE001 — damga atma, koç tekrar deneyebilsin
        db.rollback()
        raise HTTPException(status_code=500, detail={"error": "server_error", "code": "notify_failed",
                                                     "message": f"Özet hazırlanamadı: {type(e).__name__}"})
    db.commit()
    return MutationResponse(
        data=PoolParentSummarySendResult(queued=res["queued"], suppressed=res["suppressed"], sent=res["sent"],
                                         sent_at=period.parent_summary_sent_at.isoformat() if period.parent_summary_sent_at else None),
        invalidate=[*_keys(user.id, student.id)])


# ---------------------------------------------------------------- K48/K50 rehber günlük görüşme listesi

@router.get("/pool/daily", response_model=PoolDailyResponse)
def pool_daily(user: User = Depends(_require_teacher), db: Session = Depends(get_db)) -> PoolDailyResponse:
    """Bugünkü seanslar üstte; havuz öğrencileri sinyal şiddetine göre; öğrenci başına 1 ana +
    katlanan ek sinyal; Gördüm/Ertele pano uyarı akışıyla ortak (WarningState)."""
    from app.services.pool_coach_day import build_daily_list
    d = build_daily_list(db, coach=user)

    def fo(w):
        return _PFO(code=w["code"], level=w["level"], layer=w["layer"], title=w["title"], detail=w["detail"],
                    coach_only=w["coach_only"], evidence=[_PFE(**e) for e in w["evidence"]])
    rows = [PoolDailyRow(**{**r, "primary": fo(r["primary"]) if r["primary"] else None,
                            "extra": [fo(w) for w in r["extra"]], "good": [fo(w) for w in r["good"]]})
            for r in d["rows"]]
    return PoolDailyResponse(today=d["today"], rows=rows, counts=PoolDailyCounts(**d["counts"]))


# ---------------------------------------------------------------- K60 dönem geçmişi (sayfalı)

from app.routes.api_v2.schemas.pool import PoolHistoryResponse, PoolHistoryRow, PoolHistorySubject  # noqa: E402


@router.get("/students/{student_id}/pool/periods", response_model=PoolHistoryResponse)
def pool_history(student_id: int, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)) -> PoolHistoryResponse:
    """K60: dönem geçmişi sınırsız — sayfalı; her dönemde ders kırılımı, devir giriş/çıkış, seans işareti,
    veli özeti durumu."""
    student = _get_owned_student(db, student_id, user.id)
    total, rows = pm.period_history(db, student.id, offset=offset, limit=limit)
    out = [PoolHistoryRow(
        id=r["id"], opened_on=r["opened_on"].isoformat(), closed_on=_iso(r["closed_on"]),
        expected_next_on=_iso(r["expected_next_on"]), status=r["status"],
        status_label=PERIOD_STATUS_LABELS.get(r["status"], r["status"]), note=r["note"],
        total_units=r["total_units"], done_units=r["done_units"], pct=r["pct"], items_total=r["items_total"],
        items_done=r["items_done"], session_marked_units=r["session_marked_units"], carried_in=r["carried_in"],
        carried_out=r["carried_out"], has_session=r["has_session"],
        parent_summary_sent_at=_iso(r["parent_summary_sent_at"]),
        subjects=[PoolHistorySubject(**x) for x in r["subjects"]]) for r in rows]
    return PoolHistoryResponse(total=total, offset=offset, limit=limit, rows=out)


# ---------------------------------------------------------------- dönem penceresi (geçmiş dönem içi, 2026-10-13)

from app.routes.api_v2.schemas.pool import PoolPeriodDetailResponse  # noqa: E402


@router.get("/students/{student_id}/pool/periods/{period_id}", response_model=PoolPeriodDetailResponse)
def pool_period_detail(student_id: int, period_id: int, user: User = Depends(_require_teacher),
                       db: Session = Depends(get_db)) -> PoolPeriodDetailResponse:
    """Kapanmış (ya da açık) dönemin tam içeriği: kalemler (kaldırılanlar iz olarak dahil, kaba
    girip döndü sayaçları, devir) + gün gün kap görevleri (D/Y/B). Yalnız okuma."""
    from app.routes.api_v2.pool_student import period_detail_response
    student = _get_owned_student(db, student_id, user.id)
    period = db.get(StudyPeriod, period_id)
    if period is None or period.student_id != student.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "period_not_found",
                                                     "message": "Dönem bulunamadı."})
    return period_detail_response(db, period, audience="teacher")


# ---------------------------------------------------------------- dönem silme (2026-10-13)

from app.models.audit_log import AuditAction  # noqa: E402
from app.routes.api_v2.schemas.pool import PoolPeriodDeleteImpact  # noqa: E402
from app.services.audit import log_action  # noqa: E402


def _owned_period(db: Session, user: User, student_id: int, period_id: int) -> tuple[User, StudyPeriod]:
    student = _get_owned_student(db, student_id, user.id)
    p = db.get(StudyPeriod, period_id)
    if p is None or p.student_id != student.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "period_not_found",
                                                     "message": "Dönem bulunamadı."})
    return student, p


def _impact_out(p: StudyPeriod, im: pm.PeriodDeleteImpact) -> PoolPeriodDeleteImpact:
    return PoolPeriodDeleteImpact(
        period_id=p.id, deletable=not p.is_open,
        blocked_reason="Açık dönem silinemez; önce dönemi kapat." if p.is_open else None,
        items=im.items, removed_items=im.removed_items, tasks_kept=im.tasks_kept, tasks_deleted=im.tasks_deleted,
        done_units=im.done_units, session_marked_units=im.session_marked_units, carried_out=im.carried_out,
        parent_summary_sent=im.parent_summary_sent,
    )


@router.get("/students/{student_id}/pool/periods/{period_id}/delete-impact", response_model=PoolPeriodDeleteImpact)
def period_delete_impact(student_id: int, period_id: int, user: User = Depends(_require_teacher),
                         db: Session = Depends(get_db)) -> PoolPeriodDeleteImpact:
    """Silme onayı penceresi için etki: kaç kalem gider, hangi kap görevleri korunur/silinir."""
    _, p = _owned_period(db, user, student_id, period_id)
    return _impact_out(p, pm.period_delete_impact(db, p))


@router.post("/students/{student_id}/pool/periods/{period_id}/delete",
             response_model=MutationResponse[PoolBundleResponse])
def delete_period(student_id: int, period_id: int, request: Request, user: User = Depends(_require_teacher),
                  db: Session = Depends(get_db)):
    """Kapanmış dönemi sil. Öğrencinin çalıştığı kap görevleri korunur (havuz bağı kopar); dokunulmamış
    kap görevleri silinir. Açık dönem 409."""
    student, p = _owned_period(db, user, student_id, period_id)
    span = f"{p.opened_on.isoformat()} → {p.closed_on.isoformat() if p.closed_on else 'açık'}"
    try:
        im = pm.delete_period(db, p)
    except PoolError as e:
        raise _http(e, 409)
    log_action(db, action=AuditAction.USER_UPDATE, actor_id=user.id, target_type="user", target_id=student.id,
               request=request, details={"op": "pool_period_delete", "period_id": period_id, "span": span,
                                         "items": im.items, "tasks_kept": im.tasks_kept,
                                         "tasks_deleted": im.tasks_deleted, "done_units": im.done_units},
               autocommit=False)
    db.commit()
    keys = [_key(user.id, student.id), f"teacher:{user.id}:students:{student.id}", f"student:{student.id}:pool",
            f"student:{student.id}:week", f"student:{student.id}:sidebar"]
    return MutationResponse(data=get_pool(student.id, user, db), invalidate=keys)



# ---------------------------------------------------------------- "Nereden? → Öğrencinin kitapları" (2026-10-13)

from app.models.book import BOOK_TYPE_LABELS  # noqa: E402
from app.routes.api_v2.schemas.pool import PoolBookOut, PoolBookSectionOut, PoolBooksResponse  # noqa: E402


@router.get("/students/{student_id}/pool/books", response_model=PoolBooksResponse)
def pool_books(student_id: int, subject_id: int = Query(...), user: User = Depends(_require_teacher),
               db: Session = Depends(get_db)) -> PoolBooksResponse:
    """Öğrencinin bu dersteki kitapları, kitabın KENDİ bölümleriyle (kalan · havuzda bekleyen · SON).
    Rehber kitapta gördüğünü seçer; konu eşleştirmesine bakmaz. Deneme kitapları dahil."""
    student = _get_owned_student(db, student_id, user.id)
    subject = db.get(Subject, subject_id)
    if subject is None or subject.id not in {s.id for s in _subjects_for(db, student, user.id)}:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "subject_not_found",
                                                     "message": "Ders bulunamadı."})
    states = pm.student_books_for_subject(db, student, subject.id)
    tids = {x.topic_id for st in states for x in st.sections if x.topic_id}
    tnames = {t.id: t.name for t in db.query(Topic).filter(Topic.id.in_(tids)).all()} if tids else {}
    books: list[PoolBookOut] = []
    for st in states:
        newest = max((x.last_on for x in st.sections if x.last_on), default=None)
        books.append(PoolBookOut(
            book_id=st.book.id, name=st.book.name, publisher=st.book.publisher,
            type=st.book.type.value, type_label=BOOK_TYPE_LABELS.get(st.book.type, st.book.type.value),
            is_deneme=st.is_deneme,
            total_tests=sum(x.test_count for x in st.sections), completed=sum(x.completed for x in st.sections),
            sections=[PoolBookSectionOut(
                section_id=x.section_id, label=x.label, test_count=x.test_count, completed=x.completed,
                remaining=x.remaining, in_pool=x.in_pool, available=x.available,
                topic_name=tnames.get(x.topic_id) if x.topic_id else None,
                last_on=_iso(x.last_on), is_last=bool(newest and x.last_on == newest),
            ) for x in st.sections],
        ))
    return PoolBooksResponse(subject_id=subject.id, subject_name=subject.name, books=books)
