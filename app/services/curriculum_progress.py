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
    ExamSection,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    Track,
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
    unit_name: str | None = None    # ait olduğu tema/ünite (Maarif) — UI gruplama
    grade_level: int | None = None  # konunun sınıfı — UI sınıf başlığı (tekrar eden tema adı ayrımı)


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
class CurriculumProjection:
    has_exam: bool
    days_to_exam: int | None
    remaining_topics: int
    pace_per_week: float            # son 2 haftada işlenen farklı konu / 2
    projected_coverage_pct: int     # mevcut hızla sınava kadar ulaşılacak kapsama
    verdict: str                    # yetisir | risk | yetismez | sinav_yok | veri_yok


@dataclass
class CurriculumProgress:
    curriculum_model: str | None
    grade_level: int | None
    overall_total_topics: int
    overall_started_topics: int
    overall_coverage_pct: int
    subjects: list[SubjectProgress]
    extras: list[ExtraSection]       # müfredata eşleşmemiş kitap üniteleri
    projection: "CurriculumProjection | None" = None


def _status(has_resource: bool, completed: int, reserved: int, test_total: int) -> str:
    if not has_resource:
        return "kaynak_yok"
    if completed <= 0:
        return "planlandi" if reserved > 0 else "baslanmadi"
    if test_total > 0 and completed >= test_total:
        return "tamamlandi"
    return "devam"


def _compute_projection(
    db: Session, student: User, total: int, started: int,
) -> "CurriculumProjection":
    """Müfredat yetişme projeksiyonu — kapsama + sınav yakınlığı + son hız.

    Hız = son 14 günde işlenen FARKLI konu sayısı / 2 (hafta). Projeksiyon =
    started + hız × kalan hafta → sınava kadar ulaşılacak kapsama. Eşikler:
    %100 müfredat kapsaması gerçekçi değil (kimse bitirmez) → %90 tahmini
    kapsama "yetişir", %70-89 "riskli", <%70 "yetişmez". Sınav yoksa sinav_yok.
    """
    from datetime import date

    ed = student.effective_exam_date
    days = max(0, (ed - date.today()).days) if ed is not None else None
    if total <= 0:
        return CurriculumProjection(False, days, 0, 0.0, 0, "veri_yok")
    remaining = max(0, total - started)
    # son 14 günde işlenen farklı konu → hız
    recent = recently_covered_units(db, student, days=14)
    pace = round(len({c.topic_name for c in recent}) / 2.0, 1)
    if days is None:
        return CurriculumProjection(
            False, None, remaining, pace, round(100 * started / total), "sinav_yok")
    weeks = days / 7.0
    projected_started = min(total, started + pace * weeks)
    proj_pct = round(100 * projected_started / total)
    if pace <= 0 and remaining > 0:
        verdict = "yetismez"
    elif proj_pct >= 90:
        verdict = "yetisir"
    elif proj_pct >= 70:
        verdict = "risk"
    else:
        verdict = "yetismez"
    return CurriculumProjection(True, days, remaining, pace, proj_pct, verdict)


_EXAM_SECTIONS = {
    ExamSection.TYT, ExamSection.AYT_SAY, ExamSection.AYT_EA,
    ExamSection.AYT_SOZ, ExamSection.AYT_DIL,
}


def _is_exam_subject(s: Subject) -> bool:
    """Sınav-bazlı kanonik ders mi (TYT/AYT, model-bağımsız)?"""
    return s.curriculum_model is None and s.exam_section in _EXAM_SECTIONS


def _exam_base_name(name: str) -> str:
    """'TYT Matematik' / 'AYT Matematik' → 'Matematik' (okul dersiyle eşlemek için)."""
    for pfx in ("TYT ", "AYT "):
        if name.startswith(pfx):
            return name[len(pfx):].strip()
    return name


# Okul dersi adı, sınav dersi base adıyla birebir aynı değilse köprü kur.
# (örn. okul "Türk Dili ve Edebiyatı" → sınavda "Türkçe" (TYT) / "Edebiyat" (AYT)).
_SCHOOL_EXAM_SYNONYMS: dict[str, set[str]] = {
    "Türk Dili ve Edebiyatı": {"Türkçe", "Edebiyat"},
}


# YKS alanına (track) göre AYT dersleri. TYT herkese ortaktır → burada yer almaz.
TRACK_AYT_SUBJECTS: dict[Track, set[str]] = {
    Track.SAYISAL: {
        "AYT Matematik", "AYT Geometri", "AYT Fizik", "AYT Kimya", "AYT Biyoloji",
    },
    Track.EA: {
        "AYT Matematik", "AYT Geometri", "AYT Edebiyat", "AYT Tarih", "AYT Coğrafya",
    },
    Track.SOZEL: {
        "AYT Edebiyat", "AYT Tarih", "AYT Coğrafya", "AYT Felsefe Grubu",
        "AYT Din Kültürü ve Ahlak Bilgisi",
    },
    Track.DIL: set(),  # YDT (Yabancı Dil) — sistemde ayrı ders yok
}


def exam_subject_visible_for_track(s: Subject, track: Track | None) -> bool:
    """AYT sınav dersi öğrencinin alanına (track) uygun mu?

    TYT herkese görünür. AYT yalnız alanına uygun öğrenciye. Alan bilinmiyorsa
    (track None — örn. 9-10 veya henüz seçmemiş) filtre uygulanmaz (gizleme yok).
    Sınav dersi olmayan (okul) dersler etkilenmez → True.
    """
    if not _is_exam_subject(s):
        return True
    if s.exam_section == ExamSection.TYT:
        return True  # TYT tüm alanlara ortak
    if track is None:
        return True
    return s.name in TRACK_AYT_SUBJECTS.get(track, set())


def _applicable_subjects(db: Session, student: User, coach_id: int) -> list[Subject]:
    """Öğrencinin müfredat dersleri (resmi/koç) — grade + curriculum_model filtreli.

    YKS (lise/mezun) öğrenci için **sınav omurgası**: TYT/AYT kanonik dersleri
    gösterir; karşılığı olan OKUL dersini (örn. Klasik/Maarif 'Matematik') gizler
    → panel temiz "TYT/AYT müfredatında nerede". Okul müfredatı verisi silinmez,
    yalnız bu görünümde sınav dersi tercih edilir. Sınav karşılığı olmayan okul
    dersleri (henüz kanonik yok) aynen gösterilir → kademeli rollout güvenli."""
    student_cm = student.effective_curriculum_model
    rows = (
        db.query(Subject)
        .filter(or_(Subject.is_builtin.is_(True), Subject.teacher_id == coach_id))
        .order_by(Subject.order, Subject.name)
        .all()
    )
    # Aday geç: grade + model filtresi + AYT alan (track) filtresi
    candidates = [
        s for s in rows
        if s.covers_grade(student.grade_level, is_graduate=student.is_graduate)
        and not (student_cm and s.curriculum_model and s.curriculum_model != student_cm)
        and exam_subject_visible_for_track(s, student.track)
    ]
    is_yks = bool(student.is_graduate) or (
        student.grade_level is not None and student.grade_level >= 9
    )
    # YKS'de sınav dersi olan base adların okul karşılığını gizle
    exam_bases = {
        _exam_base_name(s.name) for s in candidates if _is_exam_subject(s)
    } if is_yks else set()

    out: list[Subject] = []
    seen: set[str] = set()
    for s in candidates:
        # YKS: sınav karşılığı olan okul dersini (TYT/AYT değil, modelli) atla
        if is_yks and not _is_exam_subject(s) and (
            s.name in exam_bases
            or bool(_SCHOOL_EXAM_SYNONYMS.get(s.name, set()) & exam_bases)
        ):
            continue
        if s.name in seen:  # aynı ad farklı modelden tekille (ilk geçen kalır)
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

    # Öğrencinin sınıfına kadar (kümülatif) göster — tüm müfredatı 12'ye kadar
    # dökmek mantıksız (10. sınıf öğrencisine 11-12 konuları gösterilmez). Mezun
    # veya sınıfı bilinmeyen → tümü.
    max_grade = 99 if (student.is_graduate or student.grade_level is None) else student.grade_level

    # 3) Ders bazında topic durumları
    out_subjects: list[SubjectProgress] = []
    g_total = g_started = 0
    for s in subjects:
        all_topics = topics_by_subject.get(s.id, [])
        if not all_topics:
            continue
        # Tema/ünite (parent) topic'leri yalnız GRUPLAMA içindir; "konu" sayımı +
        # durum yalnız LEAF (alt başlık) üzerinden. Düz müfredatta (LGS/Klasik)
        # tüm topic'ler parent'sız + çocuksuz → hepsi leaf. Maarif'te leaf = alt başlık.
        # Sınıf filtresi: yalnız grade_level <= öğrencinin sınıfı (kümülatif).
        parent_name_by_id = {t.id: t.name for t in all_topics}
        has_children = {t.parent_id for t in all_topics if t.parent_id is not None}
        topics = [
            t for t in all_topics
            if t.id not in has_children
            and (t.grade_level is None or t.grade_level <= max_grade)
        ]
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
                unit_name=parent_name_by_id.get(t.parent_id) if t.parent_id else None,
                grade_level=t.grade_level,
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

    projection = _compute_projection(db, student, g_total, g_started)

    return CurriculumProgress(
        curriculum_model=(student.effective_curriculum_model.value
                          if student.effective_curriculum_model else None),
        grade_level=student.grade_level,
        overall_total_topics=g_total,
        overall_started_topics=g_started,
        overall_coverage_pct=round(100 * g_started / g_total) if g_total else 0,
        subjects=out_subjects,
        extras=extras,
        projection=projection,
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


# ----------------------- Faz 3: son dönemde işlenen üniteler ------------------

@dataclass
class CoveredUnit:
    subject_name: str
    topic_name: str
    tests_completed: int


def recently_covered_units(
    db: Session, student: User, *, days: int = 7,
) -> list[CoveredUnit]:
    """Son `days` günde İŞLENEN müfredat üniteleri (seans 'geçen hafta' analizi).

    Task.date penceresi + tamamlanan (completed_count>0) section kalemleri →
    topic'e eşli olanlar → ders+konu bazında çözülen test toplamı. En çok çözülen üstte.
    """
    from datetime import date, timedelta

    from app.models import Task, TaskBookItem

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(
            Subject.name.label("subject_name"),
            Topic.name.label("topic_name"),
            func.sum(TaskBookItem.completed_count).label("tests"),
        )
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(BookSection, BookSection.id == TaskBookItem.book_section_id)
        .join(Topic, Topic.id == BookSection.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .filter(
            Task.student_id == student.id,
            Task.date >= start,
            TaskBookItem.completed_count > 0,
        )
        .group_by(Subject.name, Topic.name)
        .order_by(func.sum(TaskBookItem.completed_count).desc())
        .all()
    )
    return [
        CoveredUnit(subject_name=r.subject_name, topic_name=r.topic_name,
                    tests_completed=int(r.tests or 0))
        for r in rows
    ]
