"""LGS 5-7 tema+alt-başlık geçişi — eski düz tema topic'lerini temizle.

Bağlam: LGS Matematik/Türkçe/Fen 5-7 verisi DÜZ soyut "Tema:" adlarındaydı (yayınevi
kitaplarıyla eşleşmiyordu, %8). Yeni yapı: öğrenme alanı (PARENT) + geleneksel konu
(LEAF) → `curriculum_data.py` LGS subject'lerine `units` (5-7) eklendi, grade-8 düz
`topics` KORUNDU. Bu script eski 5-7 düz tema topic'lerini siler.

GÜVENLİ: yalnız `units` tanımlı LGS derslerinde + yalnız grade 5-7 + parent_id NULL +
ÇOCUKSUZ topic'ler ("stale" eski temalar) silinir. Yeni parent'lar (çocuklu) ve
leaf'ler (parent'lı) ve 8. sınıf düz konuları DOKUNULMAZ → grade-8 eşleşmeleri korunur.
İDEMPOTENT: stale yoksa ATLAR (start.sh güvenli). --force ile zorla, --dry-run önizle.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.models import BookSection, CurriculumModel, Subject, Topic
from scripts.curriculum_data import LGS_CURRICULUM
from scripts.seed import seed_curriculum


def main() -> int:
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    print(f"\n=== LGS 5-7 tema+alt-başlık reseed {'(DRY-RUN)' if dry else ''} ===\n")

    # Dönüştürülen dersler = LGS verisinde "units" tanımlı olanlar (Mat/Türkçe/Fen).
    converted = [name for name, spec in LGS_CURRICULUM.items() if spec.get("units")]
    if not converted:
        print("  Dönüştürülen LGS dersi yok — atlandı.")
        return 0
    print(f"  Dönüştürülen dersler: {', '.join(converted)}")

    with SessionLocal() as db:
        # 1) Yeni yapı (5-7 units + 8 topics) seed (idempotent) — eski temalar
        # veride YOK, yeniden yaratılmaz; yeni parent+leaf garanti oluşturulur.
        if not dry:
            seed_curriculum(db, only_model="LGS")

        # 2) Stale eski tema topic'lerini bul (yalnız dönüştürülen derslerde)
        stale_ids: list[int] = []
        for name in converted:
            subj = (
                db.query(Subject)
                .filter(Subject.is_builtin.is_(True), Subject.teacher_id.is_(None),
                        Subject.name == name,
                        Subject.curriculum_model == CurriculumModel.LGS)
                .first()
            )
            if not subj:
                continue
            topics = subj.topics
            has_children = {t.parent_id for t in topics if t.parent_id is not None}
            for t in topics:
                if (t.grade_level in (5, 6, 7) and t.parent_id is None
                        and t.id not in has_children):
                    stale_ids.append(t.id)

        if not stale_ids and not force:
            print("  Stale 5-7 düz tema yok — veri zaten yeni yapıda. ATLANDI.")
            return 0
        print(f"  Silinecek stale 5-7 düz tema topic: {len(stale_ids)}")

        affected = (
            db.query(BookSection).filter(BookSection.topic_id.in_(stale_ids)).all()
            if stale_ids else []
        )
        print(f"  Etkilenen book_section (NULL'lanacak, yeniden eşleştirilecek): {len(affected)}")

        if dry:
            print("\n  DRY-RUN — değişiklik yapılmadı.")
            return 0

        # 3) book_section eşleştirmelerini kopar (SQLite FK pragma kapalı → manuel)
        for s in affected:
            s.topic_id = None
        db.flush()
        # 4) bağlı review kayıtları (varsa)
        if stale_ids:
            for tbl in ("review_logs", "review_cards"):
                try:
                    db.execute(
                        text(f"DELETE FROM {tbl} WHERE topic_id IN :ids")
                        .bindparams(bindparam("ids", value=stale_ids, expanding=True))
                    )
                except Exception:
                    pass
        # 5) stale topic'leri sil
        if stale_ids:
            db.query(Topic).filter(Topic.id.in_(stale_ids)).delete(
                synchronize_session=False)
        db.commit()
        print(f"  Silindi: {len(stale_ids)} stale tema. LGS 5-7 artık öğrenme alanı + konu.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
