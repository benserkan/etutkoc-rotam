"""Aşama 2 smoke — sınav-bazlı kanonik taksonomi (TYT/AYT) + YKS dedup + eşleştirme.

A) seed_exam_curriculum idempotent → 'TYT Matematik' + 'AYT Matematik' (model-bağımsız,
   exam_section set) builtin dersleri + konuları.
B) _applicable_subjects: YKS öğrencide sınav dersi tercih edilir, okul karşılığı gizlenir
   (sınav karşılığı olmayan okul dersi aynen kalır).
C) Gerçek bir TYT Matematik kitabı (4K'nın 34 ünitesi) → seedlenen TYT konularına
   AUTO-MAP yüksek eşleşme (AI'sız, kredisiz).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, CurriculumModel, ExamSection, Subject, Topic,
    User, UserRole,
)
from app.services import curriculum_mapping as cm
from app.services.curriculum_progress import _applicable_subjects
from app.services.security import hash_password
from scripts.seed import seed_exam_curriculum

PFX = f"exam{secrets.token_hex(3)}"
PASSWORD = "Exam!2026Xy"
passed = 0
failed: list[str] = []

BOOK_UNITS = [
    "1. Ünite — Temel Kavramlar", "2. Ünite — Bölme, Bölünebilme",
    "3. Ünite — Rasyonel Sayılar", "4. Ünite — Birinci Dereceden Denklemler",
    "5. Ünite — Basit Eşitsizlikler", "6. Ünite — Üslü İfadeler",
    "7. Ünite — Köklü İfadeler", "8. Ünite — Çarpanlara Ayırma",
    "9. Ünite — Oran ve Orantı", "10. Ünite — Sayı - Kesir Problemleri",
    "11. Ünite — İşçi Problemleri", "12. Ünite — Yüzde Problemleri",
    "13. Ünite — Mantık", "14. Ünite — Kümeler", "15. Ünite — Fonksiyonlar",
    "16. Ünite — Polinomlar", "17. Ünite — Permütasyon", "18. Ünite — Olasılık",
    "19. Ünite — Veri ve İstatistik", "Tek/Çift Sayılar", "Ardışık Sayılar",
    "Asal Sayılar ve Tam Bölen Sayıları", "Faktöriyel Kavramı", "Sayı Basamakları",
    "Ebob Ekok", "Mutlak Değer", "Yaş Problemleri", "Kar Zarar Problemleri",
    "Karışım Problemleri", "Hareket Problemleri", "Grafik Problemleri",
    "Sayısal Yetenek Problemleri", "Kombinasyon", "Binom",
]


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def main() -> int:
    print(f"\n=== exam taxonomy smoke — {PFX} ===\n")

    # --- A) seed_exam_curriculum idempotent + yapı ---
    with SessionLocal() as db:
        seed_exam_curriculum(db)
        added_second = seed_exam_curriculum(db)  # ikinci kez → 0
        check("A1. ikinci seed idempotent (added=0)", added_second == 0, f"{added_second}")

        tyt = db.query(Subject).filter(
            Subject.is_builtin.is_(True), Subject.teacher_id.is_(None),
            Subject.name == "TYT Matematik", Subject.curriculum_model.is_(None),
        ).first()
        ayt = db.query(Subject).filter(
            Subject.is_builtin.is_(True), Subject.teacher_id.is_(None),
            Subject.name == "AYT Matematik", Subject.curriculum_model.is_(None),
        ).first()
        check("A2. 'TYT Matematik' dersi (model-bağımsız + exam_section TYT)",
              tyt is not None and tyt.curriculum_model is None
              and tyt.exam_section == ExamSection.TYT and tyt.available_for_graduate)
        check("A3. 'AYT Matematik' dersi (model-bağımsız + exam_section AYT)",
              ayt is not None and ayt.curriculum_model is None
              and ayt.exam_section in (ExamSection.AYT_SAY, ExamSection.AYT_EA))
        tyt_topics = db.query(Topic).filter(Topic.subject_id == tyt.id).all() if tyt else []
        ayt_topics = db.query(Topic).filter(Topic.subject_id == ayt.id).all() if ayt else []
        check("A4. TYT Matematik >= 30 konu", len(tyt_topics) >= 30, f"{len(tyt_topics)}")
        check("A5. AYT Matematik >= 10 konu", len(ayt_topics) >= 10, f"{len(ayt_topics)}")
        tyt_id = tyt.id

    # --- B) _applicable_subjects YKS dedup (izole koç-sahipli dersler) ---
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}-c@t.invalid", password_hash=hash_password(PASSWORD),
                         full_name="Koç", role=UserRole.TEACHER, is_active=True,
                         plan="solo_free", must_change_password=False)
            db.add(coach); db.flush()
            # okul Matematik (Klasik) + okul Fizik (Klasik, sınav karşılığı YOK)
            sch_mat = Subject(name=f"{PFX}Matematik", curriculum_model=CurriculumModel.KLASIK_LISE,
                              is_builtin=False, teacher_id=coach.id, min_grade_level=11,
                              max_grade_level=12, available_for_graduate=True, order=1)
            sch_fiz = Subject(name=f"{PFX}Fizik", curriculum_model=CurriculumModel.KLASIK_LISE,
                              is_builtin=False, teacher_id=coach.id, min_grade_level=11,
                              max_grade_level=12, available_for_graduate=True, order=2)
            # sınav dersleri (model-bağımsız) — base ad sch_mat ile aynı
            ex_tyt = Subject(name=f"TYT {PFX}Matematik", curriculum_model=None,
                             exam_section=ExamSection.TYT, is_builtin=False, teacher_id=coach.id,
                             min_grade_level=9, max_grade_level=12, available_for_graduate=True, order=3)
            ex_ayt = Subject(name=f"AYT {PFX}Matematik", curriculum_model=None,
                             exam_section=ExamSection.AYT_SAY, is_builtin=False, teacher_id=coach.id,
                             min_grade_level=11, max_grade_level=12, available_for_graduate=True, order=4)
            db.add_all([sch_mat, sch_fiz, ex_tyt, ex_ayt]); db.flush()
            # YKS öğrenci: 12. sınıf, 9'a 2022'de girmiş → KLASIK
            student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                           full_name="Öğr", role=UserRole.STUDENT, is_active=True,
                           teacher_id=coach.id, grade_level=12, entry_year_grade9=2022,
                           must_change_password=False)
            db.add(student); db.flush()
            db.commit()
            ids = {"coach": coach.id, "student": student.id,
                   "subjs": [sch_mat.id, sch_fiz.id, ex_tyt.id, ex_ayt.id]}

        with SessionLocal() as db:
            student = db.get(User, ids["student"])
            check("B0. öğrenci modeli KLASIK", str(student.effective_curriculum_model) ==
                  str(CurriculumModel.KLASIK_LISE), f"{student.effective_curriculum_model}")
            applicable = _applicable_subjects(db, student, ids["coach"])
            names = {s.name for s in applicable}
            check("B1. sınav dersi gösterilir (TYT + AYT)",
                  f"TYT {PFX}Matematik" in names and f"AYT {PFX}Matematik" in names, f"{names}")
            check("B2. okul Matematik GİZLENİR (sınav karşılığı var)",
                  f"{PFX}Matematik" not in names, f"{names}")
            check("B3. sınav karşılığı olmayan okul Fizik AYNEN kalır",
                  f"{PFX}Fizik" in names, f"{names}")

        # --- C) gerçek TYT kitabı → seedlenen TYT konularına yüksek auto-map ---
        with SessionLocal() as db:
            book = Book(name=f"{PFX} 4K TYT Matematik", subject_id=tyt_id,
                        type=BookType.SORU_BANKASI, teacher_id=ids["coach"])
            db.add(book); db.flush()
            for i, lbl in enumerate(BOOK_UNITS):
                db.add(BookSection(book_id=book.id, label=lbl, test_count=10, order=i))
            db.flush(); db.commit()
            ids["book"] = book.id

        with SessionLocal() as db:
            book = db.get(Book, ids["book"])
            topics = db.query(Topic).filter(Topic.subject_id == tyt_id).all()
            rows = cm.suggest_for_book(db, book, topics, use_ai=False)
            auto = sum(1 for r in rows if r["source"] == "auto")
            print(f"    → AUTO-MAP (AI'sız): {auto}/{len(BOOK_UNITS)}")
            check("C1. TYT kitabı seedlenen konulara >= 28/34 auto-eşleşme",
                  auto >= 28, f"{auto}/{len(BOOK_UNITS)}")
            check("C2. eski durumdan (1/34) belirgin iyileşme", auto >= 28)
    finally:
        with SessionLocal() as db:
            if ids.get("book"):
                db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
                db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            for sid in ids.get("subjs", []):
                db.execute(sa_delete(Topic).where(Topic.subject_id == sid))
                db.execute(sa_delete(Subject).where(Subject.id == sid))
            if ids.get("student"):
                db.execute(sa_delete(User).where(User.id == ids["student"]))
            if ids.get("coach"):
                db.execute(sa_delete(User).where(User.id == ids["coach"]))
            db.commit()
        # NOT: builtin TYT/AYT Matematik (seed) SİLİNMEZ — kalıcı üretim verisi.

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
