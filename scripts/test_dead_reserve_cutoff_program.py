"""Ölü rezerv cron'u — program haftası Pazartesi'ye hizalı değilken (2026-09-24).

Emir #113: program Perşembe–Çarşamba (17–23 Eylül). 24 Eylül sabahı cron,
program yoksa "bu Pazartesi"yi sınır aldığı için 21–23 Eylül'ün yapılmamış
testlerini rezervde bırakıyordu (koç yeni hafta açana kadar kilitli).

Senaryolar (tarihler koşu gününe göreli, `_dead_reserve_cutoff` doğrudan da
sabit tarihlerle sınanır):
  1. Program dün bitti, bugünü kapsayan program yok → dünün görevi SERBEST.
  2. Bugünün görevi (programsız gün) KORUNUR.
  3. Hiç programı olmayan öğrenci → eski kural (bu hafta korunur).
  4. Bugünü kapsayan program varsa → onun başlangıcı (değişmedi).
  5. İdempotent.

    PYTHONPATH=. python scripts/test_dead_reserve_cutoff_program.py
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject, Task,
    TaskBookItem, TaskStatus, TaskType, User, UserRole, WeeklyProgram,
)
from app.services import task_service as ts
from app.services.security import hash_password

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PFX = f"drc{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label} -- {detail}")


def _mk_student(db, teacher, name: str) -> User:
    st = User(email=f"{PFX}-{name}@t.invalid", password_hash=hash_password("X!23pass"),
              full_name=name, role=UserRole.STUDENT, is_active=True, grade_level=11,
              teacher_id=teacher.id)
    db.add(st)
    db.flush()
    return st


def _task(db, student, book, sec, day: date) -> None:
    t = Task(student_id=student.id, date=day, type=TaskType.TEST, title=f"{PFX} {day}",
             status=TaskStatus.PENDING, order=0, is_draft=False)
    db.add(t)
    db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id,
                        planned_count=2, completed_count=0))


def main() -> int:
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    yesterday = today - timedelta(days=1)
    ids: dict = {}
    with SessionLocal() as db:
        # --- saf kural (sabit tarih): Perşembe 24 Eylül, program 17–23 ---
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="T", role=UserRole.TEACHER, is_active=True, plan="solo_free")
        db.add(teacher)
        db.flush()
        a = _mk_student(db, teacher, "a")
        b = _mk_student(db, teacher, "b")
        db.add(WeeklyProgram(student_id=a.id, start_date=date(2026, 9, 17),
                             end_date=date(2026, 9, 23), coach_id=teacher.id))
        db.flush()
        thu = date(2026, 9, 24)
        mon = date(2026, 9, 21)
        check("0. saf kural: program 23'ünde bitti → sınır 24 Eylül (Pazartesi 21 değil)",
              ts._dead_reserve_cutoff(db, a.id, today=thu, this_monday=mon) == thu,
              str(ts._dead_reserve_cutoff(db, a.id, today=thu, this_monday=mon)))
        check("0b. saf kural: programsız öğrenci → bu Pazartesi",
              ts._dead_reserve_cutoff(db, b.id, today=thu, this_monday=mon) == mon)
        db.rollback()

        # --- uçtan uca: gerçek bugün ---
        teacher = User(email=f"{PFX}-t2@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="T", role=UserRole.TEACHER, is_active=True, plan="solo_free")
        db.add(teacher)
        db.flush()
        subj = Subject(name=f"{PFX} Ders", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book)
        db.flush()
        secs = [BookSection(book_id=book.id, label=f"B{i}", test_count=10, order=i)
                for i in range(3)]
        db.add_all(secs)
        db.flush()

        # A: programı dün bitti; dün + bugün görevi
        a = _mk_student(db, teacher, "a2")
        db.add(WeeklyProgram(student_id=a.id, start_date=yesterday - timedelta(days=6),
                             end_date=yesterday, coach_id=teacher.id))
        sb_a = StudentBook(student_id=a.id, book_id=book.id)
        db.add(sb_a)
        db.flush()
        sp_a_y = SectionProgress(student_book_id=sb_a.id, book_section_id=secs[0].id,
                                 reserved_count=2, completed_count=0)
        sp_a_t = SectionProgress(student_book_id=sb_a.id, book_section_id=secs[1].id,
                                 reserved_count=2, completed_count=0)
        db.add_all([sp_a_y, sp_a_t])
        _task(db, a, book, secs[0], yesterday)
        _task(db, a, book, secs[1], today)

        # B: hiç programı yok; dünkü görev (bu takvim haftasındaysa korunmalı)
        b = _mk_student(db, teacher, "b2")
        sb_b = StudentBook(student_id=b.id, book_id=book.id)
        db.add(sb_b)
        db.flush()
        sp_b = SectionProgress(student_book_id=sb_b.id, book_section_id=secs[2].id,
                               reserved_count=2, completed_count=0)
        db.add(sp_b)
        _task(db, b, book, secs[2], yesterday)
        db.commit()
        ids = {"teacher": teacher.id, "a": a.id, "b": b.id, "subj": subj.id, "book": book.id,
               "sp_a_y": sp_a_y.id, "sp_a_t": sp_a_t.id, "sp_b": sp_b.id}

    try:
        with SessionLocal() as db:
            ts.reconcile_all_active_reservations(db, today=today)
            db.commit()
            r = lambda k: db.get(SectionProgress, ids[k]).reserved_count  # noqa: E731
            check("1. program dün bitti → dünkü görevin rezervi SERBEST (yeni hafta beklenmeden)",
                  r("sp_a_y") == 0, f"got {r('sp_a_y')}")
            check("2. bugünün görevi KORUNUR", r("sp_a_t") == 2, f"got {r('sp_a_t')}")
            if yesterday >= this_monday:
                check("3. programsız öğrenci: bu haftanın görevi KORUNUR (eski kural)",
                      r("sp_b") == 2, f"got {r('sp_b')}")
            else:
                print("  [SKIP] 3. bugün Pazartesi — dün geçen haftada (ayırt edici değil)")
            ts.reconcile_all_active_reservations(db, today=today)
            db.commit()
            check("5. idempotent (ikinci koşu değişiklik yok)",
                  r("sp_a_y") == 0 and r("sp_a_t") == 2)
    finally:
        with SessionLocal() as db:
            sids = [ids["a"], ids["b"]]
            tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(sids))]
            db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
            db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
            sbs = [s.id for s in db.query(StudentBook).filter(StudentBook.student_id.in_(sids))]
            db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbs)).delete(synchronize_session=False)
            db.query(StudentBook).filter(StudentBook.id.in_(sbs)).delete(synchronize_session=False)
            db.query(WeeklyProgram).filter(WeeklyProgram.student_id.in_(sids)).delete(synchronize_session=False)
            db.query(BookSection).filter(BookSection.book_id == ids["book"]).delete(synchronize_session=False)
            db.query(Book).filter(Book.id == ids["book"]).delete(synchronize_session=False)
            db.query(Subject).filter(Subject.id == ids["subj"]).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(sids + [ids["teacher"]])).delete(synchronize_session=False)
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
