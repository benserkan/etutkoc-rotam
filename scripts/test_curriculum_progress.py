"""Müfredat ilerleme (Faz 1) smoke — hibrit omurga + durum + kapsama + ekstra.

Resmi konu omurgası + öğrencinin section ilerlemesi → durum (kaynak_yok/baslanmadi/
planlandi/devam/tamamlandi) + coverage % + frontier + eşleşmemiş ekstra.
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
    Book, BookSection, BookType, CurriculumModel, SectionProgress, StudentBook,
    Subject, Topic, User, UserRole,
)
from app.services import curriculum_progress as cp
from app.services.security import hash_password

PFX = f"cprog{secrets.token_hex(3)}"
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


def main() -> int:
    print(f"\n=== curriculum progress smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="Koç", role=UserRole.TEACHER, is_active=True, plan="solo_free")
        # 8. sınıf LGS öğrenci
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True,
                       grade_level=8, is_graduate=False)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        # Resmi LGS Matematik dersi + 4 sıralı konu (5-8 covers)
        subj = Subject(name=f"{PFX} Matematik", order=1, is_builtin=True, teacher_id=None,
                       curriculum_model=CurriculumModel.LGS, min_grade_level=5, max_grade_level=8)
        db.add(subj); db.flush()
        t1 = Topic(subject_id=subj.id, name="Çarpanlar", order=0, is_builtin=True,
                   curriculum_model=CurriculumModel.LGS, grade_level=8)
        t2 = Topic(subject_id=subj.id, name="Üslü İfadeler", order=1, is_builtin=True,
                   curriculum_model=CurriculumModel.LGS, grade_level=8)
        t3 = Topic(subject_id=subj.id, name="Olasılık", order=2, is_builtin=True,
                   curriculum_model=CurriculumModel.LGS, grade_level=8)
        t4 = Topic(subject_id=subj.id, name="Kareköklü İfadeler", order=3, is_builtin=True,
                   curriculum_model=CurriculumModel.LGS, grade_level=8)
        db.add_all([t1, t2, t3, t4]); db.flush()
        # Kitap + section'lar: t1 tamam, t2 devam, t3 planlı(0 yapıldı), t4 KAYNAK YOK
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book); db.flush()
        sec1 = BookSection(book_id=book.id, label="Çarpanlar", test_count=10, order=0, topic_id=t1.id)
        sec2 = BookSection(book_id=book.id, label="Üslü", test_count=10, order=1, topic_id=t2.id)
        sec3 = BookSection(book_id=book.id, label="Olasılık", test_count=8, order=2, topic_id=t3.id)
        sec_extra = BookSection(book_id=book.id, label="Ekstra Konu", test_count=5, order=3, topic_id=None)
        db.add_all([sec1, sec2, sec3, sec_extra]); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id); db.add(sb); db.flush()
        db.add_all([
            SectionProgress(student_book_id=sb.id, book_section_id=sec1.id, completed_count=10, reserved_count=0),
            SectionProgress(student_book_id=sb.id, book_section_id=sec2.id, completed_count=4, reserved_count=2),
            SectionProgress(student_book_id=sb.id, book_section_id=sec3.id, completed_count=0, reserved_count=3),
            SectionProgress(student_book_id=sb.id, book_section_id=sec_extra.id, completed_count=2, reserved_count=0),
        ])
        # t4 (Kareköklü) → öğrencide hiç section yok → kaynak_yok
        db.commit()
        ids = {"teacher": teacher.id, "student": student.id, "subj": subj.id, "book": book.id,
               "t1": t1.id, "t2": t2.id, "t3": t3.id, "t4": t4.id,
               "sec_extra": sec_extra.id}

    try:
        with SessionLocal() as db:
            st = db.get(User, ids["student"])
            res = cp.compute_curriculum_progress(db, st, ids["teacher"])
            check("1. müfredat modeli LGS", (res.curriculum_model or "").lower() == "lgs", res.curriculum_model)
            mat = next((s for s in res.subjects if s.subject_id == ids["subj"]), None)
            check("2. Matematik dersi var + 4 konu", mat is not None and mat.total_topics == 4,
                  f"{mat.total_topics if mat else None}")
            byt = {t.topic_id: t for t in mat.topics}
            check("3. Çarpanlar (10/10) → tamamlandi", byt[ids["t1"]].status == "tamamlandi", byt[ids["t1"]].status)
            check("4. Üslü (4/10) → devam + %40", byt[ids["t2"]].status == "devam" and byt[ids["t2"]].pct == 40,
                  f"{byt[ids['t2']].status} {byt[ids['t2']].pct}")
            check("5. Olasılık (0 yapıldı, 3 rezerv) → planlandi", byt[ids["t3"]].status == "planlandi", byt[ids["t3"]].status)
            check("6. Kareköklü (kaynak yok) → kaynak_yok + has_resource=False",
                  byt[ids["t4"]].status == "kaynak_yok" and not byt[ids["t4"]].has_resource)
            check("7. coverage: 2/4 işlendi (Çarpanlar+Üslü) → %50",
                  mat.started_topics == 2 and mat.coverage_pct == 50, f"{mat.started_topics} {mat.coverage_pct}")
            check("8. completed_topics=1 (yalnız Çarpanlar tam)", mat.completed_topics == 1, mat.completed_topics)
            check("9. frontier: son işlenen=Üslü İfadeler (order'lı en yüksek started)",
                  mat.last_topic_name == "Üslü İfadeler", mat.last_topic_name)
            check("10. frontier: sıradaki=Olasılık (ilk kaynaklı-başlanmamış)",
                  mat.next_topic_name == "Olasılık", mat.next_topic_name)
            check("11. eşleşmemiş ekstra: 'Ekstra Konu' listede",
                  any(e.section_id == ids["sec_extra"] for e in res.extras), f"{[e.label for e in res.extras]}")
            check("12. overall coverage hesaplandı (>0)", res.overall_coverage_pct > 0, res.overall_coverage_pct)
    finally:
        with SessionLocal() as db:
            secs = [s.id for s in db.query(BookSection).filter(BookSection.book_id == ids["book"]).all()]
            db.execute(sa_delete(SectionProgress).where(SectionProgress.book_section_id.in_(secs)))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
