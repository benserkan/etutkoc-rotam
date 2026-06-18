"""Öğrenci bazlı müfredat ilerleme — hibrit omurga (Faz 1).

Resmi müfredat konularını (Topic, sıralı) omurga alır; öğrencinin atanan kitap
section'larının (topic_id eşli) ilerlemesini (SectionProgress) bunlara bindirir.
Koç "müfredatta nerede + tamamlama oranı + sıradaki konu"yu görür.

Veri zinciri:
  applicable Subjects (resmi, grade+curriculum_model) → ordered Topics →
  öğrencinin o topic'e eşli section'ları (StudentBook→Book→BookSection.topic_id) →
  SectionProgress (completed/reserved) + BookSection.test_count → durum + %.

Eşleşmemiş section'lar (topic_id NULL veya müfredat dışı topic) → "ekstra" grubu
(kaybolmaz). Hiç kaynağı olmayan resmi konu → "kaynak_yok".

DURUM: kaynak_yok | baslanmadi | planlandi | devam | tamamlandi.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    User,
)


@dataclass
class TopicProgress:
    topic_id: int
    name: str
    order: int
    has_resource: bool
    test_total: int
    completed: int
    reserved: int
    status: str
    pct: int            # konu içi derinlik: completed/test_total


@dataclass
class SubjectProgress:
    subject_id: int
    name: str
    order: int
    total_topics: int
    started_topics: int      # completed>0
    completed_topics: int    # completed>=test_total (ve test_total>0)
    no_resource_topics: int
    coverage_pct: int        # started/total (müfredat işlenme oranı)
    last_topic_name: str | None      # frontier: son işlenen (en yüksek order, started)
    next_topic_name: str | None      # frontier: sıradaki (kaynaklı, başlanmamış)
    topics: list[TopicProgress] = field(default_factory=list)


@dataclass
class ExtraSection:
    section_id: int
    label: str
    book_name: str
    subject_name: str | None
    test_total: int
    completed: int


@dataclass
class CurriculumProgress:
    curriculum_model: str | None
    grade_level: int | None
    overall_total_topics: int
    overall_started_topics: int
    overall_coverage_pct: int
    subjects: list[SubjectProgress]
    extras: list[ExtraSection]       # müfredata eşleşmemiş kitap üniteleri


def _status(has_resource: bool, completed: int, reserved: int, test_total: int) -> str:
    if not has_resource:
        return "kaynak_yok"
    if completed <= 0:
        return "planlandi" if reserved > 0 else "baslanmadi"
    if test_total > 0 and completed >= test_total:
        return "tamamlandi"
    return "devam"


def _applicable_subjects(db: Session, student: User, coach_id: int) -> list[Subject]:
    """Öğrencinin müfredat dersleri (resmi/koç) — grade + curriculum_model filtreli.
    all_subjects (weekly_plan) ile aynı kural."""
    student_cm = student.effective_curriculum_model
    rows = (
        db.query(Subject)
        .filter(or_(Subject.is_builtin.is_(True), Subject.teacher_id == coach_id))
        .order_by(Subject.order, Subject.name)
        .all()
    )
    out: list[Subject] = []
    seen: set[str] = set()
    for s in rows:
        if not s.covers_grade(student.grade_level, is_graduate=student.is_graduate):
            continue
        if student_cm and s.curriculum_model and s.curriculum_model != student_cm:
            continue
        # Aynı ad farklı modelden tekille (ilk geçen kalır)
        if s.name in seen:
            continue
        seen.add(s.name)
        out.append(s)
    return out


def compute_curriculum_progress(
    db: Session, student: User, coach_id: int,
) -> CurriculumProgress:
    # 1) Öğrencinin section ilerlemesi: topic_id bazında agregat + müfredat-dışı ekstra
    rows = (
        db.query(
            BookSection.id.label("section_id"),
            BookSection.topic_id.label("topic_id"),
            BookSection.label.label("label"),
            BookSection.test_count.label("test_count"),
            Book.subject_id.label("subject_id"),
            Book.name.label("book_name"),
            func.coalesce(SectionProgress.completed_count, 0).label("completed"),
            func.coalesce(SectionProgress.reserved_count, 0).label("reserved"),
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(StudentBook.student_id == student.id)
        .all()
    )

    # topic_id → agregat (test/completed/reserved)
    by_topic: dict[int, dict] = {}
    extras: list[ExtraSection] = []
    subj_name_cache: dict[int, str] = {}
    for r in rows:
        if r.topic_id is not None:
            agg = by_topic.setdefault(
                r.topic_id, {"test": 0, "completed": 0, "reserved": 0})
            agg["test"] += int(r.test_count or 0)
            agg["completed"] += int(r.completed or 0)
            agg["reserved"] += int(r.reserved or 0)
        else:
            # eşleşmemiş ünite → ekstra (yalnız test_count>0 anlamlı)
            extras.append(ExtraSection(
                section_id=r.section_id, label=r.label, book_name=r.book_name,
                subject_name=None, test_total=int(r.test_count or 0),
                completed=int(r.completed or 0),
            ))

    # 2) Uygulanabilir dersler + sıralı konular
    subjects = _applicable_subjects(db, student, coach_id)
    subj_ids = [s.id for s in subjects]
    subj_name_cache = {s.id: s.name for s in subjects}
    topics_by_subject: dict[int, list[Topic]] = {}
    if subj_ids:
        all_topics = (
            db.query(Topic)
            .filter(
                Topic.subject_id.in_(subj_ids),
                or_(Topic.is_builtin.is_(True), Topic.teacher_id == coach_id),
            )
            .order_by(Topic.order, Topic.id)
            .all()
        )
        for t in all_topics:
            topics_by_subject.setdefault(t.subject_id, []).append(t)

    # 3) Ders bazında topic durumları
    out_subjects: list[SubjectProgress] = []
    g_total = g_started = 0
    for s in subjects:
        topics = topics_by_subject.get(s.id, [])
        if not topics:
            continue
        tps: list[TopicProgress] = []
        started = completed_topics = no_res = 0
        last_name: str | None = None
        next_name: str | None = None
        for t in topics:
            agg = by_topic.get(t.id)
            has_res = agg is not None
            test_total = agg["test"] if agg else 0
            comp = agg["completed"] if agg else 0
            resv = agg["reserved"] if agg else 0
            st = _status(has_res, comp, resv, test_total)
            pct = min(100, round(100 * comp / test_total)) if test_total > 0 else 0
            tps.append(TopicProgress(
                topic_id=t.id, name=t.name, order=t.order, has_resource=has_res,
                test_total=test_total, completed=comp, reserved=resv, status=st, pct=pct,
            ))
            if not has_res:
                no_res += 1
            if comp > 0:
                started += 1
                last_name = t.name  # order'lı → en son işlenen
            if st == "tamamlandi":
                completed_topics += 1
            if next_name is None and has_res and comp <= 0:
                next_name = t.name  # ilk kaynaklı-başlanmamış = sıradaki
        total = len(topics)
        cov = round(100 * started / total) if total else 0
        out_subjects.append(SubjectProgress(
            subject_id=s.id, name=s.name, order=s.order, total_topics=total,
            started_topics=started, completed_topics=completed_topics,
            no_resource_topics=no_res, coverage_pct=cov,
            last_topic_name=last_name, next_topic_name=next_name, topics=tps,
        ))
        g_total += total
        g_started += started

    # ekstra section'lara ders adı (book.subject_id → cache) — best effort
    if extras:
        # subject adlarını topla (müfredat dışı dersler dahil)
        extra_subj_ids = {r.subject_id for r in rows if r.topic_id is None}
        missing = [sid for sid in extra_subj_ids if sid not in subj_name_cache]
        if missing:
            for sid, nm in db.query(Subject.id, Subject.name).filter(Subject.id.in_(missing)).all():
                subj_name_cache[sid] = nm
        row_subj = {r.section_id: r.subject_id for r in rows if r.topic_id is None}
        for ex in extras:
            ex.subject_name = subj_name_cache.get(row_subj.get(ex.section_id))

    return CurriculumProgress(
        curriculum_model=(student.effective_curriculum_model.value
                          if student.effective_curriculum_model else None),
        grade_level=student.grade_level,
        overall_total_topics=g_total,
        overall_started_topics=g_started,
        overall_coverage_pct=round(100 * g_started / g_total) if g_total else 0,
        subjects=out_subjects,
        extras=extras,
    )


# ============================================================================
# Faz 2 — Sıradaki üniteler (atanabilir) + AI akıllı öncelik
# ============================================================================


@dataclass
class AssignableSection:
    book_id: int
    section_id: int
    book_name: str
    section_label: str
    test_total: int
    completed: int
    reserved: int
    remaining: int        # test_total - reserved - completed (atanabilir kapasite)


@dataclass
class NextUnit:
    subject_id: int
    subject_name: str
    topic_id: int
    topic_name: str
    order: int
    status: str           # baslanmadi | planlandi | devam
    completed: int
    test_total: int
    sections: list[AssignableSection] = field(default_factory=list)


def next_units_for_assignment(
    db: Session, student: User, coach_id: int, *, per_subject: int = 2,
) -> list[NextUnit]:
    """Her ders için SIRADAKİ atanabilir üniteler (resmi sırada, tamamlanmamış,
    kaynaklı). Her ünitenin atanabilir section'ları (kalan kapasiteli) döner →
    koç tek tıkla görev üretebilir. tamamlanmış/kaynaksız konular atlanır."""
    rows = (
        db.query(
            BookSection.id.label("section_id"),
            BookSection.topic_id.label("topic_id"),
            BookSection.label.label("label"),
            BookSection.test_count.label("test_count"),
            Book.id.label("book_id"),
            Book.name.label("book_name"),
            func.coalesce(SectionProgress.completed_count, 0).label("completed"),
            func.coalesce(SectionProgress.reserved_count, 0).label("reserved"),
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(StudentBook.student_id == student.id,
                BookSection.topic_id.isnot(None))
        .all()
    )
    # topic_id → sections + agg
    by_topic_secs: dict[int, list] = {}
    by_topic_agg: dict[int, dict] = {}
    for r in rows:
        by_topic_secs.setdefault(r.topic_id, []).append(r)
        agg = by_topic_agg.setdefault(r.topic_id, {"test": 0, "completed": 0})
        agg["test"] += int(r.test_count or 0)
        agg["completed"] += int(r.completed or 0)

    subjects = _applicable_subjects(db, student, coach_id)
    subj_ids = [s.id for s in subjects]
    topics_by_subject: dict[int, list[Topic]] = {}
    if subj_ids:
        for t in (
            db.query(Topic)
            .filter(Topic.subject_id.in_(subj_ids),
                    or_(Topic.is_builtin.is_(True), Topic.teacher_id == coach_id))
            .order_by(Topic.order, Topic.id).all()
        ):
            topics_by_subject.setdefault(t.subject_id, []).append(t)

    out: list[NextUnit] = []
    for s in subjects:
        picked = 0
        for t in topics_by_subject.get(s.id, []):
            if picked >= per_subject:
                break
            agg = by_topic_agg.get(t.id)
            if agg is None:
                continue  # kaynak yok → atla
            comp = agg["completed"]
            test_total = agg["test"]
            if test_total > 0 and comp >= test_total:
                continue  # tamamlanmış → atla
            # atanabilir section'lar (kalan kapasiteli)
            secs: list[AssignableSection] = []
            for r in by_topic_secs.get(t.id, []):
                rem = max(0, int(r.test_count or 0) - int(r.reserved or 0) - int(r.completed or 0))
                secs.append(AssignableSection(
                    book_id=r.book_id, section_id=r.section_id, book_name=r.book_name,
                    section_label=r.label, test_total=int(r.test_count or 0),
                    completed=int(r.completed or 0), reserved=int(r.reserved or 0),
                    remaining=rem,
                ))
            status = "devam" if comp > 0 else "baslanmadi"
            out.append(NextUnit(
                subject_id=s.id, subject_name=s.name, topic_id=t.id, topic_name=t.name,
                order=t.order, status=status, completed=comp, test_total=test_total,
                sections=secs,
            ))
            picked += 1
    return out


# ----------------------------- AI akıllı öncelik -----------------------------

class AIUnavailable(Exception):
    pass


def _parse_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def ai_prioritize_units(
    units: list[NextUnit],
    *,
    exam_label: str | None,
    days_to_exam: int | None,
    weak_topics: list[str],
) -> dict:
    """Gemini ile sıradaki üniteleri akıllı önceliklendir (öğrenci verili → ÜCRETLİ key).

    Girdi: deterministik sıradaki üniteler + sınav yakınlığı + zayıf konular (doğruluk).
    Çıktı: {"summary": str, "priorities": {topic_id: (priority:int, reason:str)}}.
    Öneri: resmi sıra + öğrencinin zayıf olduğu/yarım kalan + sınav yakınlığı dengesi.
    """
    from app.services import gemini

    if not units:
        return {"summary": None, "priorities": {}}
    unit_lines = "\n".join(
        f"{u.topic_id}: {u.subject_name} — {u.topic_name} "
        f"(durum: {u.status}, {u.completed}/{u.test_total} test)"
        for u in units
    )
    weak = ", ".join(weak_topics[:12]) if weak_topics else "—"
    exam_ctx = (
        f"Sınav: {exam_label or 'belirsiz'}"
        + (f", {days_to_exam} gün kaldı" if days_to_exam is not None else "")
    )
    prompt = (
        "Bir koçun öğrencisine bu hafta atayabileceği SIRADAKİ müfredat üniteleri "
        "aşağıda. Resmi müfredat sırası + öğrencinin ZAYIF olduğu konular + yarım "
        "kalanlar + sınav yakınlığını dengeleyerek ÖNCELİK sırası öner (1 = en öncelikli). "
        "Her ünite için kısa, somut gerekçe (Türkçe, 1 cümle). Klinik dil değil koçluk dili.\n\n"
        f"{exam_ctx}\n"
        f"Öğrencinin doğruluğu düşük (zayıf) konular: {weak}\n\n"
        f"SIRADAKİ ÜNİTELER (topic_id: ders — konu):\n{unit_lines}\n\n"
        'Yalnız JSON: {"summary":"1-2 cümle genel öncelik mantığı",'
        '"priorities":[{"topic_id":N,"priority":1,"reason":"..."}]}'
    )
    try:
        raw = gemini.generate(
            [gemini.text_part(prompt)],
            personal_data=True, json_mode=True, max_output_tokens=8192,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_prioritize_units gemini fail: %s", e)
        raise AIUnavailable(str(e))
    data = _parse_json(raw)
    valid = {u.topic_id for u in units}
    pri: dict[int, tuple[int, str]] = {}
    for p in (data.get("priorities") or []):
        tid = p.get("topic_id")
        if tid in valid:
            pri[int(tid)] = (int(p.get("priority") or 99), str(p.get("reason") or "").strip())
    return {"summary": str(data.get("summary") or "").strip() or None, "priorities": pri}
