"""Program "görevleriyle birlikte sil" rezervi iade eder (2026-09-27).

Saha: Zeynep Ela #164 — program silinince görevler gitti ama rezerv kaldı
(22 bölüm / 46 test "sayaç uyumsuz"). Kök neden: weekly_program_service.
delete_program `release_task_items(db, t)` yanlış imzayla çağırıyor, TypeError
geniş except'te yutuluyordu. Bu test düzeltmeyi kilitler.
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject, Task, TaskBookItem,
    TaskStatus, TaskType, User, UserRole, WeeklyProgram,
)
from app.services.section_counter_service import compute_fixes
from app.services.security import hash_password
from app.services.task_service import reserve_item
from app.services.weekly_program_service import create_program, delete_program

PFX = f"pdr_{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def main() -> int:
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("x" * 12),
                         full_name="Koç", role=UserRole.TEACHER, is_active=True)
            db.add(coach)
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x" * 12),
                      full_name="Öğr", role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                      grade_level=12)
            db.add(st)
            db.flush()
            subj = db.query(Subject).filter(Subject.is_builtin.is_(True)).first()
            book = Book(name=f"Kitap {PFX}", subject_id=subj.id, teacher_id=coach.id,
                        type=BookType.SORU_BANKASI)
            db.add(book)
            db.flush()
            s1 = BookSection(book_id=book.id, label="A", test_count=10, order=0)
            s2 = BookSection(book_id=book.id, label="B", test_count=10, order=1)
            db.add_all([s1, s2])
            db.flush()
            db.add(StudentBook(student_id=st.id, book_id=book.id))
            db.flush()
            start = date.today() + timedelta(days=30)
            prog = create_program(db, coach=coach, student_id=st.id, start=start,
                                  end=start + timedelta(days=6), allow_overlap=True)
            ids.update(coach=coach.id, student=st.id, book=book.id, prog=prog.id)

            def task(day, items, status=TaskStatus.PENDING, done=0):
                t = Task(student_id=st.id, date=start + timedelta(days=day), title="t",
                         type=TaskType.TEST, status=status)
                db.add(t)
                db.flush()
                for sec, n in items:
                    reserve_item(db, student_id=st.id, book_id=book.id, section_id=sec.id, count=n)
                    db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id,
                                        planned_count=n, completed_count=done))
                db.flush()
                return t

            task(0, [(s1, 3)])
            task(1, [(s1, 1), (s2, 2)])          # çok kalemli (karma rutin deseni)
            outside = task(10, [(s2, 4)])         # program dışı — dokunulmamalı
            db.commit()

            def reserved(sec):
                sp = (db.query(SectionProgress).join(StudentBook)
                      .filter(StudentBook.student_id == st.id,
                              SectionProgress.book_section_id == sec.id).first())
                db.refresh(sp)
                return sp.reserved_count

            check("0. başlangıç rezervi A=4 B=6", (reserved(s1), reserved(s2)) == (4, 6))
            res = delete_program(db, coach=coach, program_id=prog.id, delete_tasks=True)
            db.commit()
            check("1. programdaki 2 görev silindi", res["tasks_deleted"] == 2, str(res))
            check("2. A rezervi tamamen iade (0)", reserved(s1) == 0, str(reserved(s1)))
            check("3. B'de yalnız program dışı görevin rezervi kaldı (4)", reserved(s2) == 4,
                  str(reserved(s2)))
            check("4. program dışı görev yerinde", db.get(Task, outside.id) is not None)
            check("5. sayaç uyumsuzluğu yok", not compute_fixes(db, student_id=st.id),
                  str(compute_fixes(db, student_id=st.id)))
    finally:
        with SessionLocal() as db:
            if ids:
                tids = [t.id for t in db.query(Task).filter(Task.student_id == ids["student"])]
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids or [0])))
                db.execute(sa_delete(Task).where(Task.id.in_(tids or [0])))
                sbs = [x.id for x in db.query(StudentBook).filter(StudentBook.student_id == ids["student"])]
                db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs or [0])))
                db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
                db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id == ids["student"]))
                db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
                db.execute(sa_delete(Book).where(Book.id == ids["book"]))
                db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["coach"]])))
                db.commit()
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
