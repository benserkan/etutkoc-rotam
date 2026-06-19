"""Maarif müfredatını RESMİ MEB verisiyle yeniden kur (DESTRUCTIVE — yalnız Maarif).

Eski seed Maarif konularını yanlış/eksik yazmıştı (örn. Biyoloji 10 "Ekoloji"
teması komple eksikti, "Üç Âlem Sistemi" uydurma). `curriculum_data.py` resmi
tymm.meb.gov.tr verisiyle (tema/ünite + alt başlık) yeniden yazıldı; bu script
DB'yi o yapıya taşır.

NE YAPAR (yalnız MAARIF_LISE builtin topic'leri):
1. Etkilenen `book_sections.topic_id` → NULL (eşleştirme kopar → Faz 0 ile yeniden
   eşlenir; KARARI: otomatik yeniden eşleştir). Kaç bölüm etkilendi raporlanır.
2. Bağlı review_cards / review_logs (varsa) silinir (FSRS tekrar durumu yeniden üretilir).
3. Eski Maarif topic'leri (önce child sonra parent) silinir.
4. `seed_curriculum(only_model="MAARIF_LISE")` ile yeni tema/ünite + alt başlık eklenir.

Kullanım:
    PYTHONPATH=. python scripts/reseed_maarif_curriculum.py            # uygula
    PYTHONPATH=. python scripts/reseed_maarif_curriculum.py --dry-run  # yalnız rapor
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.models import BookSection, Topic
from app.models.curriculum import CurriculumModel
from scripts.seed import seed_curriculum


def main() -> int:
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    print(f"\n=== Maarif müfredat reseed {'(DRY-RUN)' if dry else ''} ===\n")
    with SessionLocal() as db:
        old = (
            db.query(Topic)
            .filter(Topic.is_builtin == True,  # noqa: E712
                    Topic.curriculum_model == CurriculumModel.MAARIF_LISE)
            .all()
        )
        ids = [t.id for t in old]
        # İDEMPOTENCY GUARD: yeni yapıda her parent_id=NULL Maarif topic bir TEMA
        # (çocuklu). "Stale" = parent_id=NULL ama çocuksuz (eski düz konu) → reseed
        # gerekli. Hiç stale yoksa veri zaten temiz → ATLA (start.sh güvenli;
        # tekrar çalışınca koç eşleştirmelerini yeniden NULL'lamaz). --force ile zorla.
        has_children = {t.parent_id for t in old if t.parent_id is not None}
        stale = [t for t in old if t.parent_id is None and t.id not in has_children]
        if old and not stale and not force:
            themes = sum(1 for t in old if t.parent_id is None)
            print(f"  Maarif verisi zaten yeni yapıda ({len(old)} topic, {themes} tema/ünite) "
                  f"— reseed ATLANDI (zorlamak için --force).")
            return 0
        print(f"  Eski/karışık Maarif builtin topic: {len(ids)} (stale düz konu: {len(stale)})")
        if not ids:
            print("  (eski topic yok — yalnız seed çalışacak)")
        affected = (
            db.query(BookSection).filter(BookSection.topic_id.in_(ids)).all()
            if ids else []
        )
        print(f"  Etkilenen book_section eşleştirmesi (NULL'lanacak): {len(affected)}")

        def _count(table: str) -> int:
            if not ids:
                return 0
            return db.execute(
                text(f"SELECT count(*) FROM {table} WHERE topic_id IN :ids")
                .bindparams(bindparam("ids", value=ids, expanding=True))
            ).scalar() or 0

        rc, rl = _count("review_cards"), _count("review_logs")
        print(f"  Silinecek review_cards: {rc} · review_logs: {rl}")

        if dry:
            print("\n  DRY-RUN — değişiklik yapılmadı.")
            return 0

        # 1) book_section eşleştirmelerini kopar (yeniden eşleştirme için)
        for s in affected:
            s.topic_id = None
        db.flush()
        # 2) bağlı review kayıtları
        if ids:
            for table in ("review_logs", "review_cards"):
                db.execute(
                    text(f"DELETE FROM {table} WHERE topic_id IN :ids")
                    .bindparams(bindparam("ids", value=ids, expanding=True))
                )
        # 3) eski topic'ler: önce child (parent_id dolu) sonra parent
        child_ids = [t.id for t in old if t.parent_id is not None]
        parent_ids = [t.id for t in old if t.parent_id is None]
        for batch in (child_ids, parent_ids):
            if batch:
                db.query(Topic).filter(Topic.id.in_(batch)).delete(synchronize_session=False)
        db.commit()
        print(f"  Silindi: {len(child_ids)} child + {len(parent_ids)} parent topic")

        # 4) yeni Maarif verisini seed et
        counts = seed_curriculum(db, only_model="MAARIF_LISE")
        print(f"\n  Yeni eklenen Maarif topic: {counts.get('MAARIF_LISE', 0)}")

        # doğrulama
        new = (
            db.query(Topic)
            .filter(Topic.is_builtin == True,  # noqa: E712
                    Topic.curriculum_model == CurriculumModel.MAARIF_LISE)
            .all()
        )
        themes = sum(1 for t in new if t.parent_id is None)
        leaves = sum(1 for t in new if t.parent_id is not None)
        print(f"  Toplam Maarif topic: {len(new)} ({themes} tema/ünite + {leaves} alt başlık)")
        print(f"  Eşleştirmesi kopan {len(affected)} bölüm → Faz 0 ile yeniden eşlenebilir.")

    print("\n=== tamam ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
