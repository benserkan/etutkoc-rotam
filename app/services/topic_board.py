"""Müfredat paneli — koçun "kapatayım mı?" kararının veri kaynağı (P5, 2026-09-07).

KOÇ İHTİYACI (birebir): "hangi konuya geçeceğiz? hangi konuları gördük? her
görevden ne kadar soru çözüldü, konunun çözülecek testi kaldı mı? biten
ünitenin performansını görmek isteyecek ve ek görev mi vereceğine yoksa
konuyu kapatacağına karar verecek."

Bu beş bilgi sistemde ZATEN vardı ama beş ayrı yüzeye dağılmıştı ve koç
program yaparken hiçbirini görmüyordu. Panel hepsini konu ekseninde birleştirir:

  · çözülen test + doğruluk      → topic_performance
  · kalan kapasite               → SectionProgress
  · denemede o konuda ne yaptı   → exam_topic_analysis
  · arşivde açık yanlış var mı   → wrong_question_service
  · kapatıldı mı / sıra          → topic_closure + Topic.order

KAPATMA İPUCU: sistem dört sinyali birleştirip bir ipucu üretir ama KAPATMAZ.
Karar koçundur; sistem sadece bakması gerekeni önüne koyar.
  ready   → yeterli veri + güvenilir doğruluk + denemede sorun yok + açık yanlış yok
  caution → denemede yanlış VEYA arşivde açık yanlış (Emir'in Yaş Problemleri
            vakası: görevde %96, denemede yanlış → kapatmadan önce bak)
  none    → az veri / hiç çalışılmamış

DÜRÜSTLÜK: D/Y girilmemişse doğruluk UYDURULMAZ (`accuracy_pct=None`), panel
"D/Y girilmedi" yazar. Az veriyle yüksek oran da güvenilmez — ipucu Wilson
alt sınırına bakar (2 testte %100, 20 testte %90'dan güçlü kanıt değil).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    Topic,
    User,
)
from app.services import topic_closure
from app.services.curriculum_progress import (
    _applicable_subjects,
    leaf_topics_for_student,
)
from app.services.exam_parent_summary import _wilson_lower

# Kapatmaya hazır demek için gereken en az kanıt.
MIN_TESTS_FOR_READY = 5
MIN_ANSWERED_FOR_READY = 20
READY_ACCURACY = 0.80          # Wilson alt sınırı (ham oran değil)


@dataclass
class BoardSource:
    book_id: int
    book_name: str
    section_id: int
    section_label: str
    total: int
    remaining: int
    full: bool
    completed: int = 0


@dataclass
class BoardTopic:
    topic_id: int
    name: str
    order: int
    unit_name: str | None
    status: str                    # kapali|devam|planlandi|baslanmadi|kaynak_yok
    closed: bool
    closed_at: str | None
    tests_solved: int
    correct: int
    wrong: int
    accuracy_pct: int | None       # D/Y girilmemişse None — uydurulmaz
    last_solved_at: str | None
    sourceless_completed: int
    remaining: int                 # kaynaklardaki toplam kalan kapasite
    exam_wrong: int                # son 90 günün denemelerinde yanlış sayısı
    open_wrongs: int               # arşivde açık yanlış
    readiness: str                 # ready | caution | none
    readiness_note: str
    sources: list[BoardSource] = field(default_factory=list)


@dataclass
class BoardUnmapped:
    """Müfredata BAĞLI OLMAYAN bölüm (topic_id NULL) — sayımlara girmez.

    KOÇ (2026-09-08): iki kaynaktan birinin 'Bölme ve Bölünebilme Kuralları'
    bölümü konuya bağlanmadığı için panel yalnız öteki kaynağın testini
    sayıyordu ve bunu GÖSTERMİYORDU. Artık ders başına listelenir + kitap
    sayfasındaki eşleştirme modalına link verilir.
    """
    section_id: int
    label: str
    test_count: int
    book_id: int
    book_name: str


@dataclass
class BoardSubject:
    subject_id: int
    name: str
    total_topics: int
    closed_topics: int
    coverage_pct: int
    topics: list[BoardTopic]
    unmapped: list[BoardUnmapped] = field(default_factory=list)


@dataclass
class BoardSubjectOption:
    """Ders seçici satırı — filtre uygulansa da TÜM uygulanabilir dersler.

    SAHA BUG'I (2026-09-08): ders seçilince yanıt yalnız o dersi taşıyordu →
    panel "tek ders varsa seçici gizli" kuralıyla açılır listeyi KALDIRIYORDU;
    koç başka derse dönemiyordu. Seçenek listesi artık filtreden bağımsız.
    """
    subject_id: int
    name: str
    has_source: bool


@dataclass
class TopicBoardPage:
    subjects: list[BoardSubject]
    options: list[BoardSubjectOption]


def _exam_wrong_counts(db: Session, student_id: int) -> dict[int, int]:
    """Son 90 günün denemelerinde konu başına YANLIŞ sayısı."""
    from datetime import date, timedelta

    from app.models.exam_result import (
        EQ_RESULT_YANLIS,
        ExamResult,
        ExamResultQuestion,
    )
    from app.services.exam_topic_analysis import EXAM_WEAK_WINDOW_DAYS

    cutoff = date.today() - timedelta(days=EXAM_WEAK_WINDOW_DAYS)
    rows = (
        db.query(ExamResultQuestion.topic_id, func.count(ExamResultQuestion.id))
        .join(ExamResult, ExamResult.id == ExamResultQuestion.exam_result_id)
        .filter(
            ExamResult.student_id == student_id,
            ExamResult.exam_date >= cutoff,
            ExamResultQuestion.topic_id.isnot(None),
            ExamResultQuestion.result == EQ_RESULT_YANLIS,
        )
        .group_by(ExamResultQuestion.topic_id)
        .all()
    )
    return {int(t): int(n) for t, n in rows}


def _open_wrong_counts(db: Session, student_id: int) -> dict[int, int]:
    from app.models import WrongQuestion

    rows = (
        db.query(WrongQuestion.topic_id, func.count(WrongQuestion.id))
        .filter(
            WrongQuestion.student_id == student_id,
            WrongQuestion.topic_id.isnot(None),
            WrongQuestion.status == "acik",
        )
        .group_by(WrongQuestion.topic_id)
        .all()
    )
    return {int(t): int(n) for t, n in rows}


def _readiness(
    *,
    closed: bool,
    tests: int,
    correct: int,
    wrong: int,
    exam_wrong: int,
    open_wrongs: int,
) -> tuple[str, str]:
    """Kapatma ipucu — KARAR DEĞİL, koçun bakması gerekeni söyler."""
    if closed:
        return "none", "Kapatıldı"
    if tests <= 0:
        return "none", "Henüz çalışılmadı"
    if exam_wrong > 0:
        return (
            "caution",
            f"Son denemelerde {exam_wrong} soru yanlış — kapatmadan önce bak",
        )
    if open_wrongs > 0:
        return (
            "caution",
            f"Arşivde {open_wrongs} açık yanlış var — kapatmadan önce bak",
        )
    answered = correct + wrong
    if answered < MIN_ANSWERED_FOR_READY or tests < MIN_TESTS_FOR_READY:
        return "none", "Karar için veri az"
    if _wilson_lower(correct, answered) >= READY_ACCURACY:
        pct = round(100 * correct / answered)
        return (
            "ready",
            f"{tests} test · %{pct} doğruluk · denemede sorun yok — kapatmaya hazır",
        )
    return "none", "Doğruluk henüz kapatma eşiğinin altında"


def build_topic_board(
    db: Session,
    *,
    student: User,
    coach_id: int,
    subject_id: int | None = None,
) -> TopicBoardPage:
    """Ders için konu kartları — müfredat sırasında.

    `subject_id` yoksa kaynağı olan İLK ders açılır (12. sınıfta 20+ ders var;
    hepsini hesaplamak hem yavaş hem gereksiz). `options` her durumda TÜM
    uygulanabilir dersleri taşır → ders seçici hiç kaybolmaz.
    """
    all_subjects = _applicable_subjects(db, student, coach_id)

    # --- kaynaklar (kalan kapasite) — ders seçiminden ÖNCE: seçenek sırası
    #     "kaynağı olan ders öne" kuralına bağlı (P4/P5 ile aynı ilke).
    src_rows = (
        db.query(
            BookSection.topic_id,
            BookSection.id,
            BookSection.label,
            BookSection.test_count,
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
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),
            BookSection.topic_id.isnot(None),
        )
        .all()
    )
    sources: dict[int, list[BoardSource]] = {}
    for r in src_rows:
        total = int(r.test_count or 0)
        rem = max(0, total - int(r.completed or 0) - int(r.reserved or 0))
        sources.setdefault(r.topic_id, []).append(
            BoardSource(
                book_id=r.book_id, book_name=r.book_name, section_id=r.id,
                section_label=r.label, total=total, remaining=rem,
                full=(total > 0 and rem <= 0),
                completed=int(r.completed or 0),
            )
        )
    source_subject_ids: set[int] = set()
    if sources:
        source_subject_ids = {
            int(sid)
            for (sid,) in db.query(Topic.subject_id)
            .filter(Topic.id.in_(list(sources.keys())))
            .distinct()
            .all()
        }
    ordered = sorted(
        all_subjects,
        key=lambda x: (x.id not in source_subject_ids, x.order or 0, x.name or ""),
    )
    options = [
        BoardSubjectOption(
            subject_id=x.id, name=x.name, has_source=x.id in source_subject_ids,
        )
        for x in ordered
    ]

    if subject_id is not None:
        subjects = [x for x in ordered if x.id == subject_id]
    else:
        subjects = ordered[:1]
    if not subjects:
        return TopicBoardPage(subjects=[], options=options)
    subj_ids = [s.id for s in subjects]

    # Konu kümesi TEK MERKEZDEN (müfredat sekmesi + görev kutusuyla aynı:
    # builtin/koç + LEAF + sınıf filtresi) — iki yüzey çelişmesin.
    leaf_set = leaf_topics_for_student(db, student, coach_id, subj_ids)
    parent_names = leaf_set.parent_names
    leaves = [t for sid in subj_ids for t in leaf_set.by_subject.get(sid, [])]

    # Müfredata bağlı olmayan bölümler (ders bazında) — sayıma girmez, GÖSTERİLİR.
    unmapped_rows = (
        db.query(
            BookSection.id, BookSection.label, BookSection.test_count,
            Book.id, Book.name, Book.subject_id,
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),
            BookSection.topic_id.is_(None),
            Book.subject_id.in_(subj_ids),
        )
        .order_by(Book.name, BookSection.order, BookSection.id)
        .all()
    )
    unmapped_by_subject: dict[int, list[BoardUnmapped]] = {}
    for sec_id, label, tc, bid, bname, bsid in unmapped_rows:
        unmapped_by_subject.setdefault(int(bsid), []).append(BoardUnmapped(
            section_id=sec_id, label=label, test_count=int(tc or 0),
            book_id=bid, book_name=bname,
        ))

    # --- performans (kitaplı + kaynaksız kalemler birlikte)
    from app.services.topic_performance import compute_topic_performance

    perf: dict[int, dict] = {}
    for sp in compute_topic_performance(db, student.id):
        for tp in sp.topics:
            if tp.topic_id:
                perf[tp.topic_id] = {
                    "tests": tp.tests_solved, "correct": tp.correct,
                    "wrong": tp.wrong, "accuracy": tp.accuracy_pct,
                    "last": tp.last_solved_at,
                }

    # --- kaynaksız çalışma (kitapsız ama konuya bağlı)
    sourceless_rows = (
        db.query(
            TaskBookItem.topic_id,
            func.coalesce(func.sum(TaskBookItem.completed_count), 0),
        )
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .filter(
            Task.student_id == student.id,
            TaskBookItem.book_id.is_(None),
            TaskBookItem.topic_id.isnot(None),
        )
        .group_by(TaskBookItem.topic_id)
        .all()
    )
    sourceless = {int(t): int(n or 0) for t, n in sourceless_rows}

    closures = topic_closure.closure_map(db, student.id)
    exam_wrong = _exam_wrong_counts(db, student.id)
    open_wrong = _open_wrong_counts(db, student.id)

    out: list[BoardSubject] = []
    by_subject: dict[int, list[Topic]] = {}
    for t in leaves:
        by_subject.setdefault(t.subject_id, []).append(t)

    # DERS SIRASI: kaynağı olan dersler ÖNE (P4 ile aynı ilke). 12. sınıfta
    # 20+ uygulanabilir ders olabiliyor; panel varsayılan olarak öğrencinin
    # FİİLEN çalıştığı dersi açmalı, müfredatta duran ama kitabı olmayanı değil.
    subjects_with_source = {
        t.subject_id for t in leaves if sources.get(t.id)
    }
    subjects = sorted(
        subjects,
        key=lambda x: (x.id not in subjects_with_source, x.order or 0, x.name or ""),
    )

    for s in subjects:
        rows: list[BoardTopic] = []
        closed_n = 0
        touched = 0
        for t in by_subject.get(s.id, []):
            p = perf.get(t.id) or {}
            secs = sources.get(t.id, [])
            closure = closures.get(t.id)
            is_closed = closure is not None
            tests = int(p.get("tests") or 0)
            sl = sourceless.get(t.id, 0)
            ew = exam_wrong.get(t.id, 0)
            ow = open_wrong.get(t.id, 0)
            readiness, note = _readiness(
                closed=is_closed, tests=tests,
                correct=int(p.get("correct") or 0),
                wrong=int(p.get("wrong") or 0),
                exam_wrong=ew, open_wrongs=ow,
            )
            if is_closed:
                status = "kapali"
                closed_n += 1
            elif (
                secs
                and sum(x.completed for x in secs) >= sum(x.total for x in secs) > 0
            ):
                # Sekmeyle AYNI kural (curriculum_progress._status:
                # completed >= test_total → tamamlandi). Koç kararı değil,
                # kaynağın sayacı; kapatma ayrı (P2).
                status = "tamamlandi"
            elif tests > 0 or sl > 0:
                status = "devam"
            elif secs:
                status = "baslanmadi"
            else:
                status = "kaynak_yok"
            if is_closed or tests > 0 or sl > 0:
                touched += 1
            rows.append(BoardTopic(
                topic_id=t.id, name=t.name, order=t.order,
                unit_name=parent_names.get(t.parent_id) if t.parent_id else None,
                status=status, closed=is_closed,
                closed_at=(closure.closed_at.isoformat()
                           if closure and closure.closed_at else None),
                tests_solved=tests,
                correct=int(p.get("correct") or 0),
                wrong=int(p.get("wrong") or 0),
                accuracy_pct=p.get("accuracy"),
                last_solved_at=(p.get("last").isoformat()
                                if p.get("last") else None),
                sourceless_completed=sl,
                remaining=sum(x.remaining for x in secs),
                exam_wrong=ew, open_wrongs=ow,
                readiness=readiness, readiness_note=note,
                sources=sorted(secs, key=lambda x: (x.full, -x.remaining)),
            ))
        if not rows:
            continue
        out.append(BoardSubject(
            subject_id=s.id, name=s.name, total_topics=len(rows),
            closed_topics=closed_n,
            coverage_pct=round(100 * touched / len(rows)) if rows else 0,
            topics=rows,
            unmapped=unmapped_by_subject.get(s.id, []),
        ))
    return TopicBoardPage(subjects=out, options=options)
