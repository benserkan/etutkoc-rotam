"""LGS 5-7 hibrit yapı smoke — grade-8 düz konu KORUNUR + 5-7 tema+alt-başlık.

reseed_lgs_5_7 sonrası: LGS Matematik/Türkçe/Fen → grade-8 DÜZ topics (leaf, parent
yok) + 5-7 öğrenme-alanı(parent)+konu(leaf). _accessible_topics leaf'leri verir
(parent hariç). 6. sınıf yayınevi kitabı artık auto-map eşleşir.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import BookType, CurriculumModel, Subject, Topic
from app.services import curriculum_mapping as cm
from scripts.reseed_lgs_5_7 import main as reseed_main

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


class _FakeBook:
    """suggest_for_book için minimal kitap (DB'ye yazmadan)."""
    def __init__(self, sections):
        self.sections = sections


class _FakeSection:
    def __init__(self, sid, label):
        self.id = sid
        self.label = label
        self.order = sid
        self.topic_id = None
        self.topic = None


def main() -> int:
    print("\n=== LGS 5-7 hibrit yapı smoke ===\n")
    reseed_main()  # idempotent — yeni yapıyı garanti eder
    with SessionLocal() as db:
        mat = db.query(Subject).filter(
            Subject.is_builtin.is_(True), Subject.name == "Matematik",
            Subject.curriculum_model == CurriculumModel.LGS).first()
        check("0. LGS Matematik dersi var", mat is not None)
        if not mat:
            print("=== 1 passed, 1 failed ==="); return 1
        ts = mat.topics
        child_parent_ids = {t.parent_id for t in ts if t.parent_id is not None}

        g8 = [t for t in ts if t.grade_level == 8]
        g8_flat = [t for t in g8 if t.parent_id is None and t.id not in child_parent_ids]
        check("1. grade-8 DÜZ konu korundu (>=12, parent yok = leaf)", len(g8_flat) >= 12,
              f"{len(g8_flat)}")
        check("2. grade-8 'Üslü İfadeler' var (leaf)",
              any(t.name == "Üslü İfadeler" and t.grade_level == 8 for t in g8_flat))

        parents_57 = [t for t in ts if t.grade_level in (5, 6, 7)
                      and t.parent_id is None and t.id in child_parent_ids]
        leaves_57 = [t for t in ts if t.grade_level in (5, 6, 7) and t.parent_id is not None]
        orphan_57 = [t for t in ts if t.grade_level in (5, 6, 7)
                     and t.parent_id is None and t.id not in child_parent_ids]
        check("3. 5-7 parent (öğrenme alanı, çocuklu) var", len(parents_57) >= 6, f"{len(parents_57)}")
        check("4. 5-7 leaf (konu) var", len(leaves_57) >= 20, f"{len(leaves_57)}")
        check("5. stale eski düz tema KALMADI (orphan=0)", len(orphan_57) == 0, f"{len(orphan_57)}")

        # _accessible_topics leaf verir (parent hariç)
        leaves = cm_accessible_leaf_names(db, mat.id)
        check("6. _accessible_topics 6. sınıf leaf 'Kesirlerle İşlemler' içerir",
              "Kesirlerle İşlemler" in leaves)
        check("7. _accessible_topics parent tema İÇERMEZ (öğrenme alanı aday değil)",
              not any("Öğrenme Alanı:" in n for n in leaves))

        # 6. sınıf yayınevi kitabı → auto-map eşleşir
        from app.routes.api_v2.library import _accessible_topics
        cand = _accessible_topics(db, mat.id, teacher_id=0)
        book = _FakeBook([
            _FakeSection(1, "Kesirlerle İşlemler"),
            _FakeSection(2, "Tam Sayılar"),
            _FakeSection(3, "Çarpanlar ve Katlar"),
            _FakeSection(4, "Oran"),
        ])
        rows = cm.suggest_for_book(db, book, cand, use_ai=False)
        auto = sum(1 for r in rows if r["source"] == "auto")
        check("8. 6. sınıf kitabı >=3/4 auto-eşleşme", auto >= 3, f"{auto}/4")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


def cm_accessible_leaf_names(db, subject_id):
    from app.routes.api_v2.library import _accessible_topics
    return [t.name for t in _accessible_topics(db, subject_id, teacher_id=0)]


if __name__ == "__main__":
    raise SystemExit(main())
