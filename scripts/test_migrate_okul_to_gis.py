"""migrate_okul_to_gis — geçici öğrencilerle (2026-10-27). Kuru çalışma yazmaz; uygulama
lise kayıtlarını sınıfına göre taşır, ortaokulu bırakır; ikinci koşu boş (idempotent)."""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal  # noqa: E402
from app.models import ExamResult, User  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from scripts.migrate_okul_to_gis import migrate  # noqa: E402

PFX = "migokul"
ok = 0
bad: list[str] = []


def check(label, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {label}")
    else:
        bad.append(label)
        print(f"  [FAIL] {label} ({detail})")


def cleanup(db):
    ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}_%")).all()]
    if ids:
        db.query(ExamResult).filter(ExamResult.student_id.in_(ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
    db.commit()


def main() -> int:
    with SessionLocal() as db:
        cleanup(db)
        studs = {}
        for key, grade, grad in (("g12", 12, False), ("mez", None, True), ("g10", 10, False), ("g7", 7, False)):
            u = User(email=f"{PFX}_{key}@test.invalid", full_name=f"Test {key}", role=UserRole.STUDENT,
                     password_hash="x", grade_level=grade, is_graduate=grad, is_active=True)
            db.add(u)
            db.flush()
            studs[key] = u.id
            db.add(ExamResult(student_id=u.id, title=f"Deneme {key}", exam_date=date(2026, 10, 20),
                              section=ExamSection.OKUL, total_correct=20, total_wrong=4, total_blank=16, net=19))
        db.commit()
        try:
            def sec(key):
                return db.query(ExamResult.section).filter(ExamResult.student_id == studs[key]).scalar()

            moved, skipped = migrate(db, apply=False)
            mine = {m["student_id"] for m in moved}
            check("1 kuru: 3 lise kaydı listelenir", {studs["g12"], studs["mez"], studs["g10"]} <= mine, str(moved))
            check("2 kuru: ortaokul listelenmez", studs["g7"] in {s["student_id"] for s in skipped})
            db.expire_all()
            check("3 kuru çalışma yazmaz", sec("g12") == ExamSection.OKUL)
            for sid in studs.values():
                migrate(db, apply=True, student_id=sid)
            db.expire_all()
            check("4 12. sınıf → GIS_12", sec("g12") == ExamSection.GIS_12, str(sec("g12")))
            check("5 mezun → GIS_12", sec("mez") == ExamSection.GIS_12, str(sec("mez")))
            check("6 10. sınıf → 10. sınıf gelişim izleme", sec("g10") == ExamSection.MAARIF_10, str(sec("g10")))
            check("7 ortaokul okul denemesi kalır", sec("g7") == ExamSection.OKUL, str(sec("g7")))
            again = [m for m in migrate(db, apply=False)[0] if m["student_id"] in studs.values()]
            check("8 ikinci koşu boş (idempotent)", not again, str(again))
        finally:
            cleanup(db)
    print(f"\n{ok} geçti, {len(bad)} kaldı")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
