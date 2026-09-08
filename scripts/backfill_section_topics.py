"""Bölüm → konu bağı GERİYE DÖNÜK doldurma (kaynak-konu normalizasyonu, 2026-09-08).

KOÇ: "TYT Matematik'te iki kaynak var; birinde 'Bölme Bölünebilme', diğerinde
'Bölme Bölünebilme Kuralları' yazıyor — panel yalnız adı birebir uyan yayının
test sayısını topluyor." BAĞ = BookSection.topic_id; bu betik BOŞ olanları
`curriculum_mapping` normalizasyon katmanıyla (exact · öğrenilmiş sözlük ·
kuyruk · kapsama — AI YOK, belirsizde bağlamaz) doldurur.

  python -m scripts.backfill_section_topics                 # DRY-RUN (yazmaz)
  python -m scripts.backfill_section_topics --apply         # uygular
  python -m scripts.backfill_section_topics --subject-id 32 # tek ders
  python -m scripts.backfill_section_topics --book-id 363   # tek kitap
  python -m scripts.backfill_section_topics --templates     # + katalog kayıtları

İdempotent: yalnız topic_id NULL bölümlere dokunur; ikinci koşu 0 yazar.
Prod: `docker exec -i lgs-web python -m scripts.backfill_section_topics [--apply]`.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from app.database import SessionLocal  # noqa: E402
from app.models import Book, BookSection, Subject, User  # noqa: E402
from app.models.book import BookType  # noqa: E402
from app.services import curriculum_mapping as cm  # noqa: E402


def _books_with_gaps(db, *, subject_id=None, book_id=None, coach_id=None):
    q = (
        db.query(Book)
        .join(BookSection, BookSection.book_id == Book.id)
        .filter(
            BookSection.topic_id.is_(None), Book.subject_id.isnot(None),
            # dev SQLite'ta eski test artığı geçersiz enum ('test') satırları ORM'de
            # patlatıyor → yalnız geçerli tipler (prod PG enum zaten zorlar)
            Book.type.in_(list(BookType)),
        )
    )
    if subject_id is not None:
        q = q.filter(Book.subject_id == subject_id)
    if book_id is not None:
        q = q.filter(Book.id == book_id)
    if coach_id is not None:
        q = q.filter(Book.teacher_id == coach_id)
    return q.distinct().order_by(Book.subject_id, Book.id).all()


def run(db, *, apply: bool, subject_id=None, book_id=None, coach_id=None,
        verbose: bool = True) -> dict:
    books = _books_with_gaps(db, subject_id=subject_id, book_id=book_id, coach_id=coach_id)
    subj_name = {s.id: s.name for s in db.query(Subject).all()}
    coach_name = {}
    by_source: Counter = Counter()
    per_subject_applied: Counter = Counter()
    per_subject_left: Counter = Counter()
    total_gap = 0
    rows_out = []
    for book in books:
        topics = cm.candidate_topics_for_book(db, book)
        if not topics:
            continue
        index = cm._topics_by_norm(topics)
        learned = cm.learned_label_map(db, book.subject_id, exclude_book_id=book.id)
        gaps = [s for s in (book.sections or []) if s.topic_id is None]
        total_gap += len(gaps)
        hits = []
        for sec in gaps:
            m = cm.resolve_label(sec.label, index, learned)
            if m is None:
                per_subject_left[book.subject_id] += 1
                continue
            hits.append((sec, m))
            by_source[m.source] += 1
            per_subject_applied[book.subject_id] += 1
            rows_out.append({
                "book_id": book.id, "book": book.name, "section_id": sec.id,
                "label": sec.label, "topic_id": m.topic.id, "topic": m.topic.name,
                "source": m.source,
            })
            if apply:
                sec.topic_id = m.topic.id
        if verbose and hits:
            if book.teacher_id not in coach_name:
                u = db.get(User, book.teacher_id) if book.teacher_id else None
                coach_name[book.teacher_id] = (u.full_name if u else "—")
            print(f"\n[{subj_name.get(book.subject_id, book.subject_id)}] {book.name!r} "
                  f"(kitap {book.id}, koç {coach_name[book.teacher_id]}) — "
                  f"{len(hits)}/{len(gaps)} boş bölüm bağlanıyor")
            for sec, m in hits:
                print(f"    {sec.label!r:55} → {m.topic.name!r:38} [{m.source}]")
    if apply:
        db.commit()
    print("\n" + ("UYGULANDI" if apply else "DRY-RUN (yazılmadı)"))
    print(f"  boş bölüm: {total_gap} · bağlanan: {sum(by_source.values())} "
          f"· kalan: {total_gap - sum(by_source.values())}")
    print(f"  kaynağa göre: {dict(by_source)}")
    if per_subject_applied:
        print("  ders bazında bağlanan / kalan:")
        for sid, n in per_subject_applied.most_common():
            print(f"    {subj_name.get(sid, sid)!r:40} {n:4} / {per_subject_left.get(sid, 0)}")
    return {"gap": total_gap, "applied": sum(by_source.values()), "rows": rows_out,
            "by_source": dict(by_source)}


def run_templates(db, *, apply: bool) -> int:
    """Katalog kayıtlarındaki boş bölümler (doğrulanmış + bekleyen)."""
    from app.models.book import BookTemplate
    from app.services import book_catalog

    entries = (
        db.query(BookTemplate)
        .filter(BookTemplate.catalog_status.isnot(None), BookTemplate.subject_id.isnot(None))
        .all()
    )
    n = 0
    for e in entries:
        gaps = [s for s in (e.sections or []) if s.topic_id is None]
        if not gaps:
            continue
        k = book_catalog.auto_map_sections(db, e, gaps)
        if k:
            print(f"  katalog {e.id} {e.name!r}: {k}/{len(gaps)} bağlandı")
            n += k
        if not apply:
            db.rollback()  # yazma yok
    if apply:
        db.commit()
    print(f"katalog: {n} bölüm {'bağlandı' if apply else 'bağlanabilir'}")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="yaz (varsayılan dry-run)")
    ap.add_argument("--subject-id", type=int)
    ap.add_argument("--book-id", type=int)
    ap.add_argument("--coach-id", type=int)
    ap.add_argument("--templates", action="store_true", help="katalog kayıtlarını da doldur")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    with SessionLocal() as db:
        run(db, apply=a.apply, subject_id=a.subject_id, book_id=a.book_id,
            coach_id=a.coach_id, verbose=not a.quiet)
        if a.templates:
            run_templates(db, apply=a.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
