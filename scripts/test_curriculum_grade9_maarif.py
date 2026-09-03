"""9-10. sınıf (Maarif) müfredat omurgası — saha regresyonu (2026-09-04).

VAKA: Yiğit Eren 8'den 9'a geçti. Profil doğru (grade=9, model=MAARIF_LISE)
ama müfredat paneli Maarif 9 konuları yerine **TYT konularını** gösteriyordu:
kitapları hâlâ 8. sınıf LGS kitabı olduğu için Maarif derslerinde "kaynak yok"
sayılıyor, kaynak-duyarlı dedup da sınav omurgasını (TYT) tercih ediyordu.

KURAL: sınav omurgası YALNIZ 11-12 + mezunda öne çıkar. 9-10'da okul (Maarif)
dersleri DAİMA görünür; TYT/AYT dersi ancak o derse KAYNAK atandıysa listelenir.

Senaryolar:
  1. 9. sınıf + LGS kitapları → Maarif dersi GÖRÜNÜR (asıl saha hatası)
  2. 9. sınıf → kaynaksız TYT dersi GİZLİ
  3. 9. sınıf + TYT kitabı atanmış → o TYT dersi GÖRÜNÜR (erken YKS hazırlığı)
  4. 11. sınıf → sınav omurgası korunur (TYT görünür, kaynaksız okul gizlenir)
  5. 8. sınıf (LGS) → dedup yok, okul dersleri olduğu gibi
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
    Book,
    BookSection,
    BookType,
    CurriculumModel,
    ExamSection,
    StudentBook,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services import curriculum_progress as cp
from app.services.security import hash_password

PFX = f"g9m_{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("x"),
                     full_name="G9 Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        s9 = User(email=f"{PFX}_s9@test.invalid", password_hash=hash_password("x"),
                  full_name="Dokuzuncu", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=9)
        s11 = User(email=f"{PFX}_s11@test.invalid", password_hash=hash_password("x"),
                   full_name="Onbirinci", role=UserRole.STUDENT, is_active=True,
                   teacher_id=coach.id, grade_level=11)
        s8 = User(email=f"{PFX}_s8@test.invalid", password_hash=hash_password("x"),
                  full_name="Sekizinci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=8)
        db.add_all([s9, s11, s8])
        db.flush()

        # Maarif lise "Matematik" (9-12) + TYT Matematik (sınav, model=None)
        maarif = Subject(name=f"Matematik {PFX}", teacher_id=coach.id,
                         curriculum_model=CurriculumModel.MAARIF_LISE,
                         min_grade_level=9, max_grade_level=12)
        tyt = Subject(name=f"TYT Matematik {PFX}", teacher_id=coach.id,
                      curriculum_model=None, exam_section=ExamSection.TYT,
                      min_grade_level=9, max_grade_level=12)
        lgs = Subject(name=f"Fen Bilimleri {PFX}", teacher_id=coach.id,
                      curriculum_model=CurriculumModel.LGS,
                      min_grade_level=5, max_grade_level=8)
        db.add_all([maarif, tyt, lgs])
        db.flush()
        topics = {}
        for sj in (maarif, tyt, lgs):
            tp = Topic(subject_id=sj.id, name=f"Konu {sj.id}", order=1)
            db.add(tp)
            db.flush()
            topics[sj.id] = tp.id

        # 9'un kitabı: LGS dersinde (8. sınıftan kalma) → Maarif'te kaynak YOK
        b_lgs = Book(name=f"LGS Kitap {PFX}", subject_id=lgs.id,
                     teacher_id=coach.id, type=BookType.SORU_BANKASI)
        # 11'in kitabı: okul (Maarif) dersinde → sınav karşılığı kaynaksız
        b_maarif = Book(name=f"Maarif Kitap {PFX}", subject_id=maarif.id,
                        teacher_id=coach.id, type=BookType.SORU_BANKASI)
        # erken-YKS senaryosu için TYT kitabı
        b_tyt = Book(name=f"TYT Kitap {PFX}", subject_id=tyt.id,
                     teacher_id=coach.id, type=BookType.SORU_BANKASI)
        db.add_all([b_lgs, b_maarif, b_tyt])
        db.flush()
        # NOT: "kaynak var" = bölüm müfredat KONUSUNA eşli demek
        # (_student_resource_subject_ids BookSection.topic_id üzerinden gider) —
        # yalnız kitabı atamak yetmez.
        for bk, sj in ((b_lgs, lgs), (b_maarif, maarif), (b_tyt, tyt)):
            db.add(BookSection(book_id=bk.id, label="B1", test_count=10, order=1,
                               topic_id=topics[sj.id]))
        db.flush()
        db.add(StudentBook(student_id=s9.id, book_id=b_lgs.id))
        db.add(StudentBook(student_id=s8.id, book_id=b_lgs.id))
        db.commit()
        return {
            "coach_id": coach.id, "s9": s9.id, "s11": s11.id, "s8": s8.id,
            "maarif": maarif.id, "tyt": tyt.id, "lgs": lgs.id,
            "b_lgs": b_lgs.id, "b_maarif": b_maarif.id, "b_tyt": b_tyt.id,
        }


def cleanup(d: dict) -> None:
    with SessionLocal() as db:
        sids = [d["s9"], d["s11"], d["s8"]]
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids)))
        for bid in (d["b_lgs"], d["b_maarif"], d["b_tyt"]):
            db.execute(sa_delete(BookSection).where(BookSection.book_id == bid))
            db.execute(sa_delete(Book).where(Book.id == bid))
        for sj in (d["maarif"], d["tyt"], d["lgs"]):
            db.execute(sa_delete(Topic).where(Topic.subject_id == sj))
            db.execute(sa_delete(Subject).where(Subject.id == sj))
        db.execute(sa_delete(User).where(User.id.in_(sids + [d["coach_id"]])))
        db.commit()


def names(db, student_id: int, coach_id: int) -> set[str]:
    st = db.get(User, student_id)
    return {s.name for s in cp._applicable_subjects(db, st, coach_id)}


def main() -> int:
    d = seed()
    print("\n=== 9-10 Maarif müfredat omurgası ===\n")
    try:
        with SessionLocal() as db:
            n9 = names(db, d["s9"], d["coach_id"])
            check("1. 9. sınıf + LGS kitapları → Maarif dersi GÖRÜNÜR (saha hatası)",
                  f"Matematik {PFX}" in n9, str(sorted(n9)))
            check("2. 9. sınıf → kaynaksız TYT dersi GİZLİ",
                  f"TYT Matematik {PFX}" not in n9, str(sorted(n9)))

            # 3. erken YKS: 9'a TYT kitabı ata → TYT dersi görünür olmalı
            db.add(StudentBook(student_id=d["s9"], book_id=d["b_tyt"]))
            db.commit()
            n9b = names(db, d["s9"], d["coach_id"])
            check("3. 9. sınıf + TYT kitabı → TYT dersi GÖRÜNÜR (erken YKS)",
                  f"TYT Matematik {PFX}" in n9b and f"Matematik {PFX}" in n9b,
                  str(sorted(n9b)))

            # 4. 11. sınıf: sınav omurgası korunur (kaynaksız okul gizlenir)
            n11 = names(db, d["s11"], d["coach_id"])
            check("4. 11. sınıf → sınav omurgası korunur (TYT var, okul gizli)",
                  f"TYT Matematik {PFX}" in n11 and f"Matematik {PFX}" not in n11,
                  str(sorted(n11)))

            # 5. 8. sınıf: LGS dersi görünür, lise dersleri hiç aday değil
            n8 = names(db, d["s8"], d["coach_id"])
            check("5. 8. sınıf → LGS dersi görünür, lise/sınav dersleri yok",
                  f"Fen Bilimleri {PFX}" in n8
                  and f"TYT Matematik {PFX}" not in n8
                  and f"Matematik {PFX}" not in n8,
                  str(sorted(n8)))
    finally:
        cleanup(d)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    if failed:
        for f in failed:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
