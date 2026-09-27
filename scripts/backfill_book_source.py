"""Kitap kaynağı geriye dönük doldurma (2026-09-27).

`books.source_kind` NULL olan kitaplar için kaynağı tahmin eder:
  * Aynı normalize adlı DOĞRULANMIŞ katalog kaydı var ve bölüm yapısı örtüşüyor
    → 'catalog' (koçun katalog katkısının KAYNAĞI olan kitap hariç — o elle).
  * Koçun kendi şablonuyla ad + bölüm yapısı örtüşüyor → 'template'.
  * Aksi → 'manual'.
Bölüm örtüşmesi: bölüm sayısı eşit VEYA etiketlerin ≥%60'ı ortak.

Varsayılan dry-run; yazmak için --apply. İdempotent (yalnız NULL'lara dokunur).
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import Book, BookTemplate, BookType
from app.services.book_catalog import normalized_key


def _labels(items) -> list[str]:
    return [normalized_key(x.label) for x in items]


def _overlap(book: Book, tpl: BookTemplate) -> bool:
    bl, tl = _labels(book.sections), _labels(tpl.sections)
    if not tl:
        return False
    if len(bl) == len(tl):
        return True
    common = len(set(bl) & set(tl))
    return common / max(len(tl), 1) >= 0.6


def classify(db, book: Book, catalog_by_name: dict, own_by_key: dict) -> tuple[str, int | None]:
    nn = normalized_key(book.name)
    for tpl in catalog_by_name.get(nn, []):
        if tpl.contributed_by_id == book.teacher_id and tpl.source == "coach_contribution":
            continue  # bu kitap katkının kaynağı → elle oluşturulmuş
        if _overlap(book, tpl):
            return "catalog", tpl.id
    for tpl in own_by_key.get((book.teacher_id, nn), []):
        if _overlap(book, tpl):
            return "template", tpl.id
    return "manual", None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    with SessionLocal() as db:
        catalog_by_name: dict[str, list[BookTemplate]] = {}
        own_by_key: dict[tuple, list[BookTemplate]] = {}
        for t in db.query(BookTemplate).all():
            k = t.name_normalized or normalized_key(t.name)
            if t.teacher_id is None:
                if t.catalog_status == "verified":
                    catalog_by_name.setdefault(k, []).append(t)
            else:
                own_by_key.setdefault((t.teacher_id, normalized_key(t.name)), []).append(t)
        books = (db.query(Book).filter(Book.source_kind.is_(None),
                                      Book.type.in_(list(BookType))).all())
        tally: Counter = Counter()
        for b in books:
            kind, tid = classify(db, b, catalog_by_name, own_by_key)
            tally[kind] += 1
            if a.apply:
                b.source_kind = kind
                b.source_template_id = tid
        if a.apply:
            db.commit()
        print(f"{'UYGULANDI' if a.apply else 'DRY-RUN'} · {len(books)} kitap · {dict(tally)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
