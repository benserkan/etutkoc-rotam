"""Maarif reseed sonrası eşleştirmesi kopan kitap bölümlerini OTOMATİK yeniden eşle.

Reseed (`reseed_maarif_curriculum`) eski Maarif topic'lerini sildiğinden bağlı
`book_section.topic_id`'ler NULL'landı. Bu script, müfredat modeli Maarif olan
kitapların eşleşmemiş bölümlerini yeni LEAF konulara yeniden eşler:
  - Deterministik (normalize exact) eşleşmeler → her zaman uygulanır (güvenli).
  - Gemini semantik öneri (ÜCRETSİZ key — bölüm/konu adı kişisel veri değil) →
    eşleşmeyenler için; bulunanlar uygulanır.
Koç sonradan kitap detayından "Müfredata eşleştir" ile düzeltebilir.

Kullanım:
    PYTHONPATH=. python scripts/remap_maarif_books.py --dry-run   # yalnız rapor
    PYTHONPATH=. python scripts/remap_maarif_books.py             # uygula (det. + AI)
    PYTHONPATH=. python scripts/remap_maarif_books.py --no-ai     # yalnız deterministik
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import Book, BookSection, Subject, Topic
from app.models.curriculum import CurriculumModel
from app.services.curriculum_mapping import apply_mappings, suggest_for_book


def _leaf_topics(db, subject_id: int) -> list[Topic]:
    all_t = (
        db.query(Topic)
        .filter(Topic.subject_id == subject_id, Topic.is_builtin == True)  # noqa: E712
        .order_by(Topic.order, Topic.name)
        .all()
    )
    parent_ids = {t.parent_id for t in all_t if t.parent_id is not None}
    return [t for t in all_t if t.id not in parent_ids]


def main() -> int:
    dry = "--dry-run" in sys.argv
    use_ai = "--no-ai" not in sys.argv
    print(f"\n=== Maarif kitap yeniden eşleştirme {'(DRY-RUN)' if dry else ''} "
          f"{'(AI açık)' if use_ai else '(yalnız deterministik)'} ===\n")

    with SessionLocal() as db:
        # Maarif builtin ders id'leri
        maarif_subj_ids = [
            s.id for s in db.query(Subject.id).filter(
                Subject.is_builtin == True,  # noqa: E712
                Subject.curriculum_model == CurriculumModel.MAARIF_LISE,
            ).all()
        ]
        if not maarif_subj_ids:
            print("  Maarif ders yok.")
            return 0
        # Eşleşmemiş bölümü olan + Maarif dersli kitaplar
        book_ids = [
            r[0] for r in db.query(BookSection.book_id)
            .join(Book, Book.id == BookSection.book_id)
            .filter(Book.subject_id.in_(maarif_subj_ids), BookSection.topic_id.is_(None))
            .distinct().all()
        ]
        print(f"  Eşleşmemiş bölümü olan Maarif kitabı: {len(book_ids)}")
        tot_auto = tot_ai = tot_none = 0
        for bid in book_ids:
            book = db.get(Book, bid)
            if not book or not book.sections:
                continue
            cands = _leaf_topics(db, book.subject_id)
            cand_ids = {t.id for t in cands}
            rows = suggest_for_book(db, book, cands, use_ai=use_ai)
            pairs: list[tuple[int, int]] = []
            n_auto = n_ai = n_none = 0
            for r in rows:
                if r["current_topic_id"] is not None:
                    continue
                if r["suggested_topic_id"]:
                    pairs.append((r["section_id"], r["suggested_topic_id"]))
                    if r["source"] == "auto":
                        n_auto += 1
                    else:
                        n_ai += 1
                else:
                    n_none += 1
            if not dry and pairs:
                apply_mappings(db, book, pairs, cand_ids)
                db.commit()
            tot_auto += n_auto; tot_ai += n_ai; tot_none += n_none
            print(f"  #{bid} {book.name[:42]:42s} auto={n_auto} ai={n_ai} eşleşmedi={n_none}")

        print(f"\n  TOPLAM: deterministik={tot_auto} · AI={tot_ai} · eşleşmedi={tot_none}")
        if dry:
            print("  DRY-RUN — değişiklik yapılmadı.")
        else:
            print("  Uygulandı. Eşleşmeyenleri koç 'Müfredata eşleştir' ile tamamlar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
