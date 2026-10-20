"""Koç kitabının bölümlerini güncel katalog kaydından yeniden kurar.

Katalog kaydı yeniden yapılandırıldığında (ör. tema düzeyi → müfredat alt
başlığı) o kayıttan daha önce kopyalanmış koç kitaplarını hizalar. YALNIZ
bölümlere hiçbir kayıt bağlı değilse çalışır (görev kalemi, ilerleme sayacı,
bağımsız çalışma, yanlış soru, talep, şablon, havuz…) — aksi halde dokunmaz.
Atamalar korunur; her atama için yeni bölümlere sıfır SectionProgress açılır.

Kullanım:
  python -m scripts.resync_book_from_catalog --book 693 --template 325 [--apply]
Varsayılan dry-run.
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import text

from app.database import SessionLocal
from app.models import Book, BookSection, BookTemplate, SectionProgress, StudentBook

# book_sections'a FK veren tablolar (section_progress hariç — o ayrıca kontrol edilir)
_REFS = [
    ("task_book_items", "book_section_id"),
    ("self_study_entries", "book_section_id"),
    ("wrong_questions", "book_section_id"),
    ("task_template_items", "book_section_id"),
    ("pool_items", "book_section_id"),
    ("skeleton_ghost_actions", "section_id"),
    ("suggestion_feedback", "book_section_id"),
    ("task_requests", "proposed_section_id"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, required=True)
    ap.add_argument("--template", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    with SessionLocal() as db:
        book = db.get(Book, a.book)
        tpl = db.get(BookTemplate, a.template)
        assert book and tpl, "kitap ya da katalog kaydı yok"
        assert tpl.catalog_status == "verified", "katalog kaydı verified değil"
        assert book.subject_id == tpl.subject_id, "ders farklı"
        sec_ids = [s.id for s in book.sections]
        if sec_ids:
            ids = ",".join(str(i) for i in sec_ids)
            for table, col in _REFS:
                n = db.execute(text(f"select count(*) from {table} where {col} in ({ids})")).scalar()
                if n:
                    print(f"DUR: {table} tablosunda {n} bağlı kayıt var — dokunulmadı.")
                    return 1
            used = (db.query(SectionProgress)
                    .filter(SectionProgress.book_section_id.in_(sec_ids))
                    .filter((SectionProgress.reserved_count > 0) | (SectionProgress.completed_count > 0))
                    .count())
            if used:
                print(f"DUR: {used} bölümde ilerleme/rezerv var — dokunulmadı.")
                return 1

        sbs = db.query(StudentBook).filter_by(book_id=book.id).all()
        old_n, old_t = len(sec_ids), sum(s.test_count or 0 for s in book.sections)
        if sec_ids:
            db.query(SectionProgress).filter(SectionProgress.book_section_id.in_(sec_ids)).delete(
                synchronize_session=False)
            db.query(BookSection).filter(BookSection.id.in_(sec_ids)).delete(synchronize_session=False)
        db.flush()
        new = []
        for ts in sorted(tpl.sections, key=lambda x: x.order):
            s = BookSection(book_id=book.id, label=ts.label, test_count=ts.default_test_count,
                            order=ts.order, topic_id=ts.topic_id)
            db.add(s)
            new.append(s)
        db.flush()
        for sb in sbs:
            for s in new:
                db.add(SectionProgress(student_book_id=sb.id, book_section_id=s.id,
                                       reserved_count=0, completed_count=0))
        book.source_template_id = tpl.id
        print(f"{book.name}: {old_n} bölüm/{old_t} test → {len(new)} bölüm/"
              f"{sum(s.test_count or 0 for s in new)} test · {len(sbs)} atama korundu")
        if a.apply:
            db.commit()
            print("UYGULANDI.")
        else:
            db.rollback()
            print("DRY-RUN — değişiklik yazılmadı (--apply).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
