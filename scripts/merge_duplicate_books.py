"""Aynı öğrencide aynı adı taşıyan kopya kitap kayıtlarını birleştirir (2026-09-29).

  python -m scripts.merge_duplicate_books            # KURU çalışma (yalnız plan)
  python -m scripts.merge_duplicate_books --apply    # tek işlemde uygular

Kural (güvenli olmayanlara dokunulmaz):
  • Grup = aynı öğrenci + aynı ders + aynı ad (boşluk/büyük-küçük harf duyarsız), aktif atama.
  • Kalan kayıt = ilk atanan. Kopyanın bölüm yapısı (sıra, ad, test sayısı) BİREBİR olmalı.
  • Kopya kitap başka bir öğrenciye de atanmışsa atlanır.
  • Kopyaya bağlı her kayıt (görev kalemi, yanlış soru, iskelet satırı, talep, şablon,
    öneri geri bildirimi, bağımsız çalışma, iskelet hayalet kaydı, kitap seti) kalan
    kitabın EŞLEŞEN bölümüne taşınır; ilerleme sayaçları toplanır.
  • Kopya atama ve kopya kitap en sonda silinir; silmeden önce kalan referans aranır.
"""
from __future__ import annotations

import sys
from collections import defaultdict

from sqlalchemy import text

from app.database import SessionLocal
from app.models import Book, BookSection, SectionProgress, StudentBook

BOOK_COLS = [
    ("task_book_items", "book_id"), ("wrong_questions", "book_id"),
    ("suggestion_feedback", "book_id"), ("task_template_items", "book_id"),
    ("weekly_skeleton_slots", "book_id"), ("weekly_skeleton_slots", "second_book_id"),
    ("task_requests", "proposed_book_id"),
]
SECTION_COLS = [
    ("task_book_items", "book_section_id"), ("wrong_questions", "book_section_id"),
    ("suggestion_feedback", "book_section_id"), ("task_template_items", "book_section_id"),
    ("skeleton_ghost_actions", "section_id"), ("task_requests", "proposed_section_id"),
    ("self_study_entries", "book_section_id"),
]


def norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def sections(db, book_id):
    return (db.query(BookSection).filter(BookSection.book_id == book_id)
            .order_by(BookSection.order, BookSection.id).all())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    apply = "--apply" in argv
    only = [int(a.split("=", 1)[1]) for a in argv if a.startswith("--student=")]
    db = SessionLocal()
    try:
        q = (db.query(StudentBook, Book).join(Book, Book.id == StudentBook.book_id)
             .filter(StudentBook.archived_at.is_(None)))
        if only:
            q = q.filter(StudentBook.student_id.in_(only))
        rows = q.all()
        groups: dict[tuple, list] = defaultdict(list)
        for sb, b in rows:
            groups[(sb.student_id, b.subject_id, norm(b.name))].append((sb, b))
        merged = 0
        for key, items in sorted(groups.items()):
            if len(items) < 2:
                continue
            items.sort(key=lambda x: (x[0].assigned_at, x[0].id))
            keep_sb, keep_b = items[0]
            keep_secs = sections(db, keep_b.id)
            sig = [(norm(s.label), s.test_count) for s in keep_secs]
            print(f"Öğrenci #{key[0]} · '{keep_b.name}' → kalan kitap #{keep_b.id}")
            for dup_sb, dup_b in items[1:]:
                dup_secs = sections(db, dup_b.id)
                if [(norm(s.label), s.test_count) for s in dup_secs] != sig:
                    print(f"   #{dup_b.id}: bölüm yapısı farklı — ATLANDI")
                    continue
                others = (db.query(StudentBook).filter(StudentBook.book_id == dup_b.id,
                                                       StudentBook.id != dup_sb.id).count())
                if others:
                    print(f"   #{dup_b.id}: başka {others} atamada kullanılıyor — ATLANDI")
                    continue
                smap = {d.id: k.id for d, k in zip(dup_secs, keep_secs)}
                # 1) kitap referansları
                for tbl, col in BOOK_COLS:
                    n = db.execute(text(f"UPDATE {tbl} SET {col} = :k WHERE {col} = :d"),
                                   {"k": keep_b.id, "d": dup_b.id}).rowcount
                    if n:
                        print(f"   {tbl}.{col}: {n} satır #{dup_b.id} → #{keep_b.id}")
                # kitap seti: aynı sette ikisi varsa kopya satır silinir
                db.execute(text("DELETE FROM book_set_items WHERE book_id = :d AND set_id IN "
                                "(SELECT set_id FROM book_set_items WHERE book_id = :k)"),
                           {"k": keep_b.id, "d": dup_b.id})
                n = db.execute(text("UPDATE book_set_items SET book_id = :k WHERE book_id = :d"),
                               {"k": keep_b.id, "d": dup_b.id}).rowcount
                if n:
                    print(f"   book_set_items: {n} satır taşındı")
                # 2) bölüm referansları
                for tbl, col in SECTION_COLS:
                    for d_id, k_id in smap.items():
                        n = db.execute(text(f"UPDATE {tbl} SET {col} = :k WHERE {col} = :d"),
                                       {"k": k_id, "d": d_id}).rowcount
                        if n:
                            print(f"   {tbl}.{col}: {n} satır bölüm #{d_id} → #{k_id}")
                db.execute(text("UPDATE self_study_entries SET student_book_id = :k WHERE student_book_id = :d"),
                           {"k": keep_sb.id, "d": dup_sb.id})
                # 3) ilerleme sayaçları toplanır
                keep_sp = {sp.book_section_id: sp for sp in
                           db.query(SectionProgress).filter(SectionProgress.student_book_id == keep_sb.id)}
                for sp in db.query(SectionProgress).filter(SectionProgress.student_book_id == dup_sb.id).all():
                    k_sec = smap[sp.book_section_id]
                    tgt = keep_sp.get(k_sec)
                    if tgt is None:
                        tgt = SectionProgress(student_book_id=keep_sb.id, book_section_id=k_sec,
                                              reserved_count=0, completed_count=0, manual_count=0)
                        db.add(tgt)
                        keep_sp[k_sec] = tgt
                    if sp.completed_count or sp.reserved_count or (sp.manual_count or 0):
                        print(f"   ilerleme bölüm #{k_sec}: çözülen +{sp.completed_count}, "
                              f"rezerv +{sp.reserved_count}, elle +{sp.manual_count or 0}")
                    tgt.completed_count += sp.completed_count
                    tgt.reserved_count += sp.reserved_count
                    tgt.manual_count = (tgt.manual_count or 0) + (sp.manual_count or 0)
                    db.delete(sp)
                db.flush()
                # 4) kopya atama + kopya kitap
                db.delete(dup_sb)
                db.flush()
                left = sum(db.execute(text(f"SELECT COUNT(*) FROM {t} WHERE {c} = :d"), {"d": dup_b.id}).scalar()
                           for t, c in BOOK_COLS + [("book_set_items", "book_id"), ("student_books", "book_id")])
                if left:
                    print(f"   #{dup_b.id}: {left} referans kaldı — kitap SİLİNMEDİ (yalnız atama kaldırıldı)")
                else:
                    db.delete(dup_b)
                    print(f"   kopya kitap #{dup_b.id} silindi")
                merged += 1
        if apply:
            db.commit()
            print(f"\n{merged} kopya birleştirildi (UYGULANDI).")
        else:
            db.rollback()
            print(f"\n{merged} kopya birleştirilecek (KURU çalışma — değişiklik yok).")
        return merged
    finally:
        db.close()


if __name__ == "__main__":
    main()
