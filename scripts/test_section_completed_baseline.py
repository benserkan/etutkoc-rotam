# -*- coding: utf-8 -*-
"""Bölüm 'zaten çözüldü' baseline endpoint smoke (geçmiş yıl ayıklama)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException
from app.database import SessionLocal
from app.models import (User, UserRole, Book, BookType, BookSection, StudentBook,
                        SectionProgress, Subject)
from app.routes.api_v2.teacher import teacher_set_section_completed_v2, _student_book_summary
from app.routes.api_v2.schemas.teacher import SectionCompletedBaselineBody
from app.services.security import hash_password

PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print(f"  [PASS] {n}")
    else: FAIL += 1; print(f"  [FAIL] {n} {e}")

db = SessionLocal()
SUF = "_secbaseline_tmp"
def clean():
    for u in db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all():
        for b in db.query(Book).filter(Book.teacher_id == u.id).all():
            sbids = [sb.id for sb in db.query(StudentBook).filter(StudentBook.book_id == b.id).all()]
            if sbids: db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbids)).delete(synchronize_session=False)
            db.query(StudentBook).filter(StudentBook.book_id == b.id).delete(synchronize_session=False)
            db.query(BookSection).filter(BookSection.book_id == b.id).delete(synchronize_session=False)
        db.query(Book).filter(Book.teacher_id == u.id).delete(synchronize_session=False)
        db.query(Subject).filter(Subject.teacher_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.commit()
clean()
try:
    coach = User(email=f"c{SUF}@x.com", full_name="C", role=UserRole.TEACHER, password_hash=hash_password("x"), is_active=True)
    db.add(coach); db.flush()
    stu = User(email=f"s{SUF}@x.com", full_name="S", role=UserRole.STUDENT, password_hash=hash_password("x"), is_active=True, teacher_id=coach.id)
    db.add(stu); db.flush()
    subj = Subject(teacher_id=coach.id, name="Mat", order=1); db.add(subj); db.flush()
    book = Book(teacher_id=coach.id, name="345 SB", type=BookType.SORU_BANKASI, subject_id=subj.id); db.add(book); db.flush()
    sec1 = BookSection(book_id=book.id, label="Unite 1", test_count=20, order=0); db.add(sec1)
    sec2 = BookSection(book_id=book.id, label="Unite 2", test_count=30, order=1); db.add(sec2)
    db.flush()
    sb = StudentBook(student_id=stu.id, book_id=book.id); db.add(sb); db.flush()
    db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec1.id, reserved_count=0, completed_count=0))
    db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec2.id, reserved_count=5, completed_count=0))  # sec2'de 5 rezerv
    db.commit()

    # 1) Unite 1'i TAM çözülmüş işaretle (20) → kalan 0
    res = teacher_set_section_completed_v2(stu.id, sb.id, sec1.id, SectionCompletedBaselineBody(completed_count=20), coach, db)
    s1 = next(x for x in res.data.sections if x.section_id == sec1.id)
    check("1. Unite 1 completed=20", s1.completed_count == 20, f"got {s1.completed_count}")
    rem1 = s1.test_count - s1.completed_count - s1.reserved_count
    check("2. Unite 1 kalan=0 (atanmaz)", rem1 == 0, f"got {rem1}")

    # 2) Kısmi: Unite 2'yi 10 çözülmüş işaretle (rezerv 5 var, max 25)
    res2 = teacher_set_section_completed_v2(stu.id, sb.id, sec2.id, SectionCompletedBaselineBody(completed_count=10), coach, db)
    s2 = next(x for x in res2.data.sections if x.section_id == sec2.id)
    check("3. Unite 2 completed=10 (kısmi)", s2.completed_count == 10, f"got {s2.completed_count}")
    check("4. Unite 2 kalan=15 (30-10-5)", (s2.test_count - s2.completed_count - s2.reserved_count) == 15)

    # 3) Sınır aşımı: Unite 2'ye 26 (max 25) → 422
    try:
        teacher_set_section_completed_v2(stu.id, sb.id, sec2.id, SectionCompletedBaselineBody(completed_count=26), coach, db)
        check("5. sınır aşımı 422", False, "exception bekleniyordu")
    except HTTPException as ex:
        check("5. sınır aşımı 422 (rezerv korunur)", ex.status_code == 422)

    # 4) İşareti kaldır: Unite 1'i 0'a çek → tüm bölüm tekrar atanabilir
    res4 = teacher_set_section_completed_v2(stu.id, sb.id, sec1.id, SectionCompletedBaselineBody(completed_count=0), coach, db)
    s1b = next(x for x in res4.data.sections if x.section_id == sec1.id)
    check("6. işaret kaldırıldı (completed=0, kalan=20)", s1b.completed_count == 0 and (s1b.test_count - s1b.reserved_count) == 20)

    # 5) Cross-tenant: başka koç → 404
    other = User(email=f"o{SUF}@x.com", full_name="O", role=UserRole.TEACHER, password_hash=hash_password("x"), is_active=True)
    db.add(other); db.flush()
    try:
        teacher_set_section_completed_v2(stu.id, sb.id, sec1.id, SectionCompletedBaselineBody(completed_count=5), other, db)
        check("7. cross-tenant 404", False)
    except HTTPException as ex:
        check("7. cross-tenant 404 (başka koç erişemez)", ex.status_code == 404)
finally:
    clean(); db.close()
print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
