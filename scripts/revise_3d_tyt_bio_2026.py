"""3D TYT Biyoloji — 2026 baskısına geçiş (2026-10-11, koç isteği).

1) KATALOG: verified "3D TYT Biyoloji Soru Bankası" kaydının bölümleri
   data/kitap-katalog/3d_tyt_biyoloji.json'daki 2026 yapısıyla YERİNDE
   değiştirilir (kayıt id'si korunur → kitapların kaynak bağı kopmaz).
2) KOÇ KİTABI (--book N): öğrencinin geldiği yere kadar (--keep-through etiketi
   dahil) bölümlere DOKUNULMAZ; sonraki bölümler silinip JSON'daki --from
   etiketinden itibaren yeni baskının bölümleri eklenir. Silinecek bölümlerde
   görev kalemi / çözülmüş ya da rezerve test / başka bir referans varsa
   HİÇBİR ŞEY yapılmaz (güvenlik).

  python -m scripts.revise_3d_tyt_bio_2026 --book 374            # kuru çalışma
  python -m scripts.revise_3d_tyt_bio_2026 --book 374 --apply
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookTemplate, BookTemplateSection, SectionProgress, StudentBook, Topic,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON = os.path.join(ROOT, "data/kitap-katalog/3d_tyt_biyoloji.json")
KEEP_THROUGH = "Canlı Âlemleri ve Özellikleri / Hayvanlar - Virüsler"
FROM_LABEL = "Bire Bir ÖSYM (CANLILAR DÜNYASI)"


def arg(name: str) -> str | None:
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    return None


def topic_id(db, subject_id: int, name: str | None) -> int | None:
    if not name:
        return None
    t = db.query(Topic).filter(Topic.subject_id == subject_id, Topic.name == name).first()
    if t is None:
        raise SystemExit(f"HATA: '{name}' konusu ders #{subject_id} içinde yok")
    return t.id


def section_refs(db, ids: list[int]) -> dict[str, int]:
    """book_sections.id'ye işaret eden TÜM tablolarda bu bölümlere kaç satır var."""
    out: dict[str, int] = {}
    if not ids:
        return out
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name == "book_sections" and table.name != "book_sections":
                    n = db.execute(
                        text(f'SELECT COUNT(*) FROM "{table.name}" WHERE "{col.name}" IN ({",".join(map(str, ids))})')
                    ).scalar()
                    if n:
                        out[f"{table.name}.{col.name}"] = n
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    book_id = arg("--book")
    data = json.load(open(JSON, encoding="utf-8"))
    secs = data["sections"]
    print(f"Yeni baskı: {len(secs)} bölüm · {sum(s['test_count'] for s in secs)} test\n")

    with SessionLocal() as db:
        # ---- 1) katalog
        tpl = (db.query(BookTemplate)
               .filter(BookTemplate.name == data["name"], BookTemplate.teacher_id.is_(None))
               .first())
        if tpl is None:
            raise SystemExit("HATA: katalog kaydı bulunamadı")
        old = sorted(tpl.sections, key=lambda s: s.order)
        print(f"KATALOG #{tpl.id} '{tpl.name}' durum={tpl.catalog_status}: "
              f"{len(old)} bölüm / {sum(s.default_test_count for s in old)} test → "
              f"{len(secs)} / {sum(s['test_count'] for s in secs)}")
        new_tpl = [(s["label"], s["test_count"], topic_id(db, tpl.subject_id, s.get("topic"))) for s in secs]
        if apply:
            for s in old:
                db.delete(s)
            db.flush()
            for i, (lab, cnt, tid) in enumerate(new_tpl):
                db.add(BookTemplateSection(template_id=tpl.id, label=lab, default_test_count=cnt,
                                           order=i, topic_id=tid))
            if hasattr(tpl, "warnings") and "warnings" in data:
                pass  # uyarılar JSON'da (provenance) — modelde alan yok

        # ---- 2) koç kitabı
        if book_id:
            book = db.get(Book, int(book_id))
            if book is None:
                raise SystemExit("HATA: kitap yok")
            bsecs = (db.query(BookSection).filter(BookSection.book_id == book.id)
                     .order_by(BookSection.order, BookSection.id).all())
            labels = [s.label for s in bsecs]
            if KEEP_THROUGH not in labels:
                raise SystemExit(f"HATA: '{KEEP_THROUGH}' kitapta yok")
            cut = labels.index(KEEP_THROUGH)
            keep, drop = bsecs[: cut + 1], bsecs[cut + 1:]
            start = [s["label"] for s in secs].index(FROM_LABEL)
            add = secs[start:]
            print(f"\nKİTAP #{book.id} '{book.name}' — korunan {len(keep)} bölüm "
                  f"(son: {keep[-1].label}), silinecek {len(drop)}, eklenecek {len(add)}")
            drop_ids = [s.id for s in drop]
            sps = db.query(SectionProgress).filter(SectionProgress.book_section_id.in_(drop_ids)).all()
            busy = [sp for sp in sps if (sp.completed_count or 0) > 0 or (sp.reserved_count or 0) > 0]
            refs = section_refs(db, drop_ids)
            refs.pop("section_progress.book_section_id", None)
            if busy or refs:
                print(f"DUR: silinecek bölümlerde ilerleme/referans var → {len(busy)} ilerleme, {refs}")
                db.rollback()
                return 1
            for s in drop:
                print(f"  - {s.test_count:2d}  {s.label}")
            for s in add:
                print(f"  + {s['test_count']:2d}  {s['label']}  → {s.get('topic') or '—'}")
            print(f"  toplam test: {sum(s.test_count for s in bsecs)} → "
                  f"{sum(s.test_count for s in keep) + sum(s['test_count'] for s in add)}")
            if apply:
                for sp in sps:
                    db.delete(sp)
                for s in drop:
                    db.delete(s)
                db.flush()
                sbs = db.query(StudentBook).filter(StudentBook.book_id == book.id).all()
                base = (keep[-1].order or 0) + 1
                for i, s in enumerate(add):
                    ns = BookSection(book_id=book.id, label=s["label"], test_count=s["test_count"],
                                     order=base + i, topic_id=topic_id(db, book.subject_id, s.get("topic")))
                    db.add(ns)
                    db.flush()
                    for sb in sbs:
                        db.add(SectionProgress(student_book_id=sb.id, book_section_id=ns.id,
                                               reserved_count=0, completed_count=0))
        if apply:
            db.commit()
            print("\nUYGULANDI.")
        else:
            db.rollback()
            print("\n(kuru çalışma — --apply ile uygula)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
