"""Görev ekleme kutusunun veri kaynağı (P4, 2026-09-07).

TASARIM: koç "türev çalışsın" diye düşünür, "345'in 12. ünitesi" diye değil.
Bu yüzden arama birimi KONU; kaynaklar konunun altında listelenir ve her
konunun altında sabit bir "kaynak belirtmeden ver" seçeneği vardır.

Bugüne kadar bu bilgi üç ayrı uçta dağınıktı (müfredat / öneri motoru /
kitap-bölüm ağacı) ve koç program yaparken hiçbirini tek ekranda görmüyordu.

Gruplar:
  · curriculum → müfredatta sıradaki açık konular (Topic.order)
  · weak       → zayıflık sinyali olanlar (tekrar kartı · yanlış arşivi · deneme)
  · recent     → son 21 günde çalışılmış konular (koç genelde aynı yerden devam eder)

Arama (q) verilirse gruplama kalkar, tek düz liste döner: konu adı, kitap adı
ve bölüm etiketi birlikte aranır.

KAPASİTESİ DOLU BÖLÜM GİZLENMEZ (P1 kararı): `full` bayrağıyla işaretlenir,
koç yine seçebilir. Envanter yardımcıdır, otorite değil.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

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
from app.services import task_quantity, topic_closure
from app.services.curriculum_progress import (
    _applicable_subjects,
    leaf_topics_for_student,
)

# Grup başına en fazla kaç konu gösterilir (kutu kısa kalmalı).
CURRICULUM_PER_SUBJECT = 2
# Toplam tavan: 12. sınıf öğrencisinde 23 uygulanabilir ders olabiliyor —
# ders başına 2 konu 46 satır eder, kutu kullanılamaz hâle gelir. Koç aradığını
# arama kutusundan bulur; açılıştaki liste KISA olmalı.
CURRICULUM_LIMIT = 12
WEAK_LIMIT = 6
RECENT_LIMIT = 6
OTHER_LIMIT = 6
SEARCH_LIMIT = 25

RECENT_WINDOW_DAYS = 21


@dataclass
class PickerSource:
    book_id: int
    book_name: str
    section_id: int
    section_label: str
    total: int
    remaining: int
    full: bool          # kapasite doldu — GİZLENMEZ, işaretlenir (P1)


@dataclass
class PickerItem:
    topic_id: int
    topic_name: str
    subject_id: int
    subject_name: str
    status: str
    badge: str | None            # "sıradaki" | "zayıf" | "son çalışılan"
    quantity: int                # koçun bu derste tipik verdiği sayı (P3)
    quantity_reason: str
    sources: list[PickerSource] = field(default_factory=list)
    theme_name: str | None = None  # üst başlık (tema/ünite) — "neden çıktı" ipucu
    grade_level: int | None = None
    match: str | None = None       # arama: "tam" | "kısmi" | "tema"
    # 2026-10-30 (saha, Neslihan Hoca): "topic" = sınıf müfredatı konusu ·
    # "outside" = öğrenciye ATANMIŞ kitabın başka müfredattaki konusu (ör. 8. sınıfa
    # TYT kitabı) · "unmapped" = kitabın konusu bağlanmamış bölümü (topic_id < 0
    # sahte kimlik = −section_id; kaynaksız verilemez, yalnız kitaptan).
    kind: str = "topic"


@dataclass
class PickerGroup:
    key: str
    label: str
    items: list[PickerItem]


def _sources_by_topic(db: Session, student_id: int) -> dict[int, list[PickerSource]]:
    rows = (
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
            StudentBook.student_id == student_id,
            StudentBook.archived_at.is_(None),
            BookSection.topic_id.isnot(None),
        )
        .all()
    )
    out: dict[int, list[PickerSource]] = {}
    for r in rows:
        total = int(r.test_count or 0)
        remaining = max(0, total - int(r.completed or 0) - int(r.reserved or 0))
        out.setdefault(r.topic_id, []).append(
            PickerSource(
                book_id=r.book_id, book_name=r.book_name,
                section_id=r.id, section_label=r.label,
                total=total, remaining=remaining,
                full=(total > 0 and remaining <= 0),
            )
        )
    return out


def _unmapped_sources(db: Session, student_id: int) -> list[tuple[PickerSource, int, str]]:
    """Öğrenciye atanmış kitaplarda konusu BAĞLANMAMIŞ bölümler (+ kitabın dersi).

    Görev kutusu konu ekseninde çalıştığı için bu bölümler hiç görünmüyordu;
    koç "Eşleşen konu yok" görüp kitabın kütüphanede olmadığını sanıyordu."""
    rows = (
        db.query(
            BookSection.id, BookSection.label, BookSection.test_count,
            Book.id.label("book_id"), Book.name.label("book_name"),
            Book.subject_id, Subject.name.label("subject_name"),
            func.coalesce(SectionProgress.completed_count, 0).label("completed"),
            func.coalesce(SectionProgress.reserved_count, 0).label("reserved"),
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(Subject, Subject.id == Book.subject_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.archived_at.is_(None),
            BookSection.topic_id.is_(None),
        )
        .order_by(Book.name, BookSection.order, BookSection.id)
        .all()
    )
    out: list[tuple[PickerSource, int, str]] = []
    for r in rows:
        total = int(r.test_count or 0)
        remaining = max(0, total - int(r.completed or 0) - int(r.reserved or 0))
        out.append((
            PickerSource(book_id=r.book_id, book_name=r.book_name, section_id=r.id,
                         section_label=r.label, total=total, remaining=remaining,
                         full=(total > 0 and remaining <= 0)),
            r.subject_id, r.subject_name,
        ))
    return out


def _weak_topic_ids(db: Session, student: User) -> dict[int, float]:
    """Zayıflık sinyalleri — öneri motorunun kullandığı üç kaynak.

    Hepsi best-effort: biri patlarsa kutu yine açılır (koçun işi durmaz).
    """
    scores: dict[int, float] = {}
    for loader in (
        lambda: _review_map(db, student.id),
        lambda: _wrong_map(db, student.id),
        lambda: _exam_map(db, student.id),
    ):
        try:
            for topic_id, score in (loader() or {}).items():
                scores[topic_id] = max(scores.get(topic_id, 0.0), float(score))
        except Exception:  # noqa: BLE001 — sinyal yoksa kutu yine çalışmalı
            continue
    return scores


def _review_map(db: Session, student_id: int) -> dict[int, float]:
    from app.services.review_scheduler import struggling_topic_ids_map

    return struggling_topic_ids_map(db, student_id=student_id)


def _wrong_map(db: Session, student_id: int) -> dict[int, float]:
    from app.services.wrong_question_service import open_wrong_topic_map

    return open_wrong_topic_map(db, student_id)


def _exam_map(db: Session, student_id: int) -> dict[int, float]:
    from app.services.exam_topic_analysis import exam_weak_topic_map

    return exam_weak_topic_map(db, student_id)


def _recent_topic_ids(db: Session, student_id: int) -> list[int]:
    since = date.today() - timedelta(days=RECENT_WINDOW_DAYS)
    rows = (
        db.query(BookSection.topic_id, func.max(Task.date).label("last"))
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(BookSection, BookSection.id == TaskBookItem.book_section_id)
        .filter(
            Task.student_id == student_id,
            Task.date >= since,
            BookSection.topic_id.isnot(None),
        )
        .group_by(BookSection.topic_id)
        .order_by(func.max(Task.date).desc())
        .limit(RECENT_LIMIT * 2)
        .all()
    )
    sourceless = (
        db.query(TaskBookItem.topic_id, func.max(Task.date).label("last"))
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .filter(
            Task.student_id == student_id,
            Task.date >= since,
            TaskBookItem.book_id.is_(None),
            TaskBookItem.topic_id.isnot(None),
        )
        .group_by(TaskBookItem.topic_id)
        .order_by(func.max(Task.date).desc())
        .limit(RECENT_LIMIT * 2)
        .all()
    )
    merged: dict[int, date] = {}
    for topic_id, last in list(rows) + list(sourceless):
        if topic_id is None:
            continue
        if topic_id not in merged or last > merged[topic_id]:
            merged[topic_id] = last
    return [t for t, _ in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)]


def build_task_picker(
    db: Session,
    *,
    student: User,
    coach_id: int,
    q: str | None = None,
) -> list[PickerGroup]:
    """Görev kutusunun içeriği. `q` verilirse gruplama yerine düz arama."""
    subjects = _applicable_subjects(db, student, coach_id)
    if not subjects:
        return []
    subj_by_id = {s.id: s for s in subjects}
    subj_ids = list(subj_by_id)

    # Konu kümesi TEK MERKEZDEN (sekme + hafta paneliyle aynı: builtin/koç +
    # LEAF + sınıf filtresi). Tema/ünite başlıkları atanabilir birim değil.
    leaf_set = leaf_topics_for_student(db, student, coach_id, subj_ids)
    leaf_topics = [t for sid in subj_ids for t in leaf_set.by_subject.get(sid, [])]

    sources = _sources_by_topic(db, student.id)
    closed = topic_closure.closed_topic_ids(db, student.id)
    weak = _weak_topic_ids(db, student)

    # Miktar önerisi ders başına BİR KEZ hesaplanır (konu başına sorgu atmayalım)
    qty_cache: dict[int, task_quantity.QuantitySuggestion] = {}

    def qty(subject_id: int) -> task_quantity.QuantitySuggestion:
        if subject_id not in qty_cache:
            qty_cache[subject_id] = task_quantity.learned_quantity(
                db, coach_id=coach_id, subject_id=subject_id, student_id=student.id,
            )
        return qty_cache[subject_id]

    def make(topic: Topic, badge: str | None, kind: str = "topic") -> PickerItem:
        secs = sources.get(topic.id, [])
        sug = qty(topic.subject_id)
        subj = subj_by_id.get(topic.subject_id) or topic.subject
        if topic.id in closed:
            status = "tamamlandi"
        elif secs:
            status = "devam" if any(s.remaining < s.total for s in secs) else "baslanmadi"
        else:
            status = "kaynak_yok"
        return PickerItem(
            topic_id=topic.id, topic_name=topic.name,
            subject_id=topic.subject_id,
            subject_name=(subj.name if subj else "—"),
            status=status, badge=badge,
            quantity=sug.quantity, quantity_reason=sug.reason,
            sources=sorted(secs, key=lambda s: (s.full, -s.remaining)),
            theme_name=leaf_set.parent_names.get(topic.parent_id) if topic.parent_id else None,
            grade_level=topic.grade_level,
            kind=kind,
        )

    # Atanmış kitapların müfredat DIŞI konuları + konusu bağlanmamış bölümler
    leaf_ids = {t.id for t in leaf_topics}
    outside_ids = [tid for tid in sources if tid not in leaf_ids]
    outside_topics = (
        db.query(Topic).filter(Topic.id.in_(outside_ids)).order_by(Topic.order, Topic.id).all()
        if outside_ids else []
    )
    unmapped = _unmapped_sources(db, student.id)

    def make_unmapped(src: PickerSource, subject_id: int, subject_name: str) -> PickerItem:
        sug = qty(subject_id)
        return PickerItem(
            topic_id=-src.section_id, topic_name=src.section_label,
            subject_id=subject_id, subject_name=subject_name,
            status="baslanmadi" if src.remaining >= src.total else "devam",
            badge="konusu bağlı değil", quantity=sug.quantity, quantity_reason=sug.reason,
            sources=[src], kind="unmapped",
        )

    # ---- Arama modu: gruplama yok — sezgisel, yazım hatasına dayanıklı (2026-10-16)
    #      Eski sürüm sorguyu TEK PARÇA, harfi harfine arıyordu: "milli desten"
    #      "Millî Bir Destan"ı bulamıyordu. topic_search: sözcük bazlı, sıra
    #      önemsiz, baş harf + yazım hatası toleransı, tema adı alt konuları getirir.
    if q and q.strip():
        from app.services.topic_search import SearchDoc, search

        own = student.grade_level
        docs = []
        for t in leaf_topics:
            secs = sources.get(t.id, [])
            subj = subj_by_id.get(t.subject_id)
            bonus = (0.03 if (own is not None and t.grade_level == own) else 0.0)
            bonus += 0.02 if secs else 0.0
            bonus -= 0.05 if t.id in closed else 0.0
            docs.append(SearchDoc(
                key=t.id, name=t.name,
                theme=leaf_set.parent_names.get(t.parent_id) if t.parent_id else None,
                subject=subj.name if subj else None,
                extra=" ".join(f"{s.book_name} {s.section_label}" for s in secs),
                bonus=bonus,
            ))
        for t in outside_topics:
            secs = sources.get(t.id, [])
            docs.append(SearchDoc(
                key=t.id, name=t.name, theme=None,
                subject=t.subject.name if t.subject else None,
                extra=" ".join(f"{s.book_name} {s.section_label}" for s in secs),
                bonus=0.01,
            ))
        for src, _sid, sname in unmapped:
            docs.append(SearchDoc(
                key=-src.section_id, name=src.section_label, theme=None,
                subject=sname, extra=src.book_name, bonus=0.0,
            ))
        topic_by_id = {t.id: t for t in leaf_topics}
        outside_by_id = {t.id: t for t in outside_topics}
        unmapped_by_key = {-src.section_id: (src, sid, sname) for src, sid, sname in unmapped}
        hits = []
        for h in search(q, docs, SEARCH_LIMIT):
            if h.key in unmapped_by_key:
                it = make_unmapped(*unmapped_by_key[h.key])
            elif h.key in outside_by_id:
                it = make(outside_by_id[h.key], "başka müfredat", kind="outside")
            else:
                it = make(topic_by_id[h.key], "kapalı" if h.key in closed else None)
            it.match = "tema" if h.via_theme else ("tam" if h.full else "kısmi")
            hits.append(it)
        return [PickerGroup(key="search", label="Arama sonuçları", items=hits)]

    # ---- Grup 1: müfredatta sıradaki (ders başına ilk N açık konu)
    #
    # DERS SIRASI: kaynağı olan dersler ÖNE alınır. Koç o kitapları atadıysa
    # öğrenci fiilen o derslerle çalışıyordur; hiç kaynağı olmayan ders
    # (müfredatta var ama kitabı yok) listenin sonuna düşer.
    topics_by_subject: dict[int, list[Topic]] = {}
    for t in leaf_topics:
        topics_by_subject.setdefault(t.subject_id, []).append(t)
    subjects_with_source = {
        t.subject_id for t in leaf_topics if sources.get(t.id)
    }
    ordered_subjects = sorted(
        subjects,
        key=lambda s: (s.id not in subjects_with_source, s.order or 0, s.name or ""),
    )

    curriculum_items: list[PickerItem] = []
    for subj in ordered_subjects:
        if len(curriculum_items) >= CURRICULUM_LIMIT:
            break
        picked = 0
        for t in topics_by_subject.get(subj.id, []):
            if picked >= CURRICULUM_PER_SUBJECT:
                break
            if len(curriculum_items) >= CURRICULUM_LIMIT:
                break
            if t.id in closed:
                continue
            secs = sources.get(t.id, [])
            # Tamamen bitmiş konuyu "sıradaki" diye gösterme
            if secs and all(s.full for s in secs):
                continue
            picked += 1
            curriculum_items.append(make(t, "sıradaki"))

    # ---- Grup 2: zayıflık sinyali olanlar
    topic_by_id = {t.id: t for t in leaf_topics}
    weak_items = [
        make(topic_by_id[tid], "zayıf")
        for tid, _ in sorted(weak.items(), key=lambda kv: -kv[1])
        if tid in topic_by_id and tid not in closed
    ][:WEAK_LIMIT]

    # ---- Grup 3: son çalışılanlar (koç genelde aynı yerden devam eder)
    seen = {i.topic_id for i in curriculum_items} | {i.topic_id for i in weak_items}
    recent_items = [
        make(topic_by_id[tid], "son çalışılan")
        for tid in _recent_topic_ids(db, student.id)
        if tid in topic_by_id and tid not in seen and tid not in closed
    ][:RECENT_LIMIT]

    # ---- Grup 4: atanmış kitapların müfredat dışı konuları + bağlanmamış bölümler
    #      (kutu açılınca da görünsün — koç aramadan "kitap nerede?" diye kalmasın)
    other_items: list[PickerItem] = [
        make(t, "başka müfredat", kind="outside")
        for t in outside_topics
        if t.id not in closed and any(not s.full for s in sources.get(t.id, []))
    ][:OTHER_LIMIT]
    for src, sid, sname in unmapped:
        if len(other_items) >= OTHER_LIMIT * 2:
            break
        if not src.full:
            other_items.append(make_unmapped(src, sid, sname))

    groups = [
        PickerGroup(key="curriculum", label="Müfredatta sıradaki", items=curriculum_items),
        PickerGroup(key="weak", label="Zayıf · tekrar gereken", items=weak_items),
        PickerGroup(key="recent", label="Son çalıştıkların", items=recent_items),
        PickerGroup(key="other_books", label="Atanmış kitapların diğer bölümleri", items=other_items),
    ]
    return [g for g in groups if g.items]
