# -*- coding: utf-8 -*-
"""Görev kaleminde BOŞ sayısı (blank_count) smoke — 2026-08-17.

Senaryolar (10):
   1. Öğrenci set-completed D/Y/B → kalem blank_count kaydedilir
   2. Öğrenci gün görünümünde blank döner
   3. Kitapsız denemede c+w+b > completed → 422 invalid_result_distribution
   4. Kitapsız denemede c+w+b == completed → 200
   5. complete (tek kalem) blank ile → kaydedilir
   6. uncomplete → blank_count NULL'a döner
   7. Koç /result blank ile düzeltir → kaydedilir
   8. Koç gün görünümü blank_count döner
   9. Negatif blank → 422
  10. blank göndermeden güncelleme → mevcut blank KORUNUR (sentinel None)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"blank_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
T1 = f"{PFX}_t@test.invalid"
S1 = f"{PFX}_s@test.invalid"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed():
    today = date.today()
    with SessionLocal() as db:
        t = User(email=T1, password_hash=hash_password(PASSWORD),
                 full_name=f"{PFX} Koç", role=UserRole.TEACHER, is_active=True)
        db.add(t)
        db.flush()
        s = User(email=S1, password_hash=hash_password(PASSWORD),
                 full_name=f"{PFX} Öğr", role=UserRole.STUDENT,
                 teacher_id=t.id, is_active=True, grade_level=8)
        db.add(s)
        db.flush()
        subj = Subject(name=f"{PFX} Mat", teacher_id=t.id)
        db.add(subj)
        db.flush()
        b = Book(name=f"{PFX} SB", subject_id=subj.id, teacher_id=t.id,
                 type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        sec = BookSection(book_id=b.id, label="Bölüm 1", order=1, test_count=10)
        db.add(sec)
        db.flush()
        sb = StudentBook(student_id=s.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=4, completed_count=0))
        # Kitaplı görev (4 test)
        task1 = Task(student_id=s.id, title=f"{PFX} Test görevi",
                     type=TaskType.TEST, date=today, status=TaskStatus.PENDING,
                     is_draft=False)
        db.add(task1)
        db.flush()
        db.add(TaskBookItem(task_id=task1.id, book_id=b.id,
                            book_section_id=sec.id, planned_count=4))
        # Kitapsız deneme (20 soru)
        task2 = Task(student_id=s.id, title=f"{PFX} Deneme", type=TaskType.OTHER,
                     date=today, status=TaskStatus.PENDING, is_draft=False)
        db.add(task2)
        db.flush()
        db.add(TaskBookItem(task_id=task2.id, book_id=None,
                            book_section_id=None, label="Deneme",
                            planned_count=20))
        db.commit()
        i1 = db.query(TaskBookItem).filter_by(task_id=task1.id).first().id
        i2 = db.query(TaskBookItem).filter_by(task_id=task2.id).first().id
        return {"t": t.id, "s": s.id, "task1": task1.id, "item1": i1,
                "task2": task2.id, "item2": i2, "today": today.isoformat(),
                "book": b.id, "sb": sb.id}


def _cleanup(ids):
    with SessionLocal() as db:
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_([ids["task1"], ids["task2"]])))
        db.execute(sa_delete(Task).where(Task.id.in_([ids["task1"], ids["task2"]])))
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id == ids["sb"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == ids["sb"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
        db.execute(sa_delete(Book).where(Book.id == ids["book"]))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == ids["t"]))
        db.execute(sa_delete(User).where(User.id.in_([ids["t"], ids["s"]])))
        db.commit()


def _blank_of(item_id):
    with SessionLocal() as db:
        return db.get(TaskBookItem, item_id).blank_count


def main() -> int:
    ids = _seed()
    c = TestClient(app)
    get_login_limiter().reset()
    r = c.post("/api/v2/auth/login", json={"email": S1, "password": PASSWORD})
    assert r.status_code == 200, r.text

    try:
        # 1-2: kitaplı kalem D/Y/B
        r = c.post(f"/api/v2/student/tasks/{ids['task1']}/items/{ids['item1']}/set-completed",
                   json={"completed": 4, "correct": 30, "wrong": 6, "blank": 4})
        check("1. set-completed D/Y/B → 200 + blank kaydedildi",
              r.status_code == 200 and _blank_of(ids["item1"]) == 4,
              f"{r.status_code} blank={_blank_of(ids['item1'])}")
        r = c.get(f"/api/v2/student/day?date={ids['today']}")
        item = next(it for t in r.json()["tasks"] if t["id"] == ids["task1"]
                    for it in t["items"])
        check("2. gün görünümünde blank döner", item.get("blank") == 4,
              str(item.get("blank")))

        # 3-4: kitapsız deneme kuralı
        r = c.post(f"/api/v2/student/tasks/{ids['task2']}/items/{ids['item2']}/set-completed",
                   json={"completed": 20, "correct": 12, "wrong": 5, "blank": 5})
        check("3. denemede c+w+b > completed → 422",
              r.status_code == 422
              and r.json()["detail"]["code"] == "invalid_result_distribution",
              str(r.status_code))
        r = c.post(f"/api/v2/student/tasks/{ids['task2']}/items/{ids['item2']}/set-completed",
                   json={"completed": 20, "correct": 12, "wrong": 5, "blank": 3})
        check("4. denemede c+w+b == completed → 200",
              r.status_code == 200 and _blank_of(ids["item2"]) == 3,
              f"{r.status_code} blank={_blank_of(ids['item2'])}")

        # 5-6: complete + uncomplete
        r = c.post(f"/api/v2/student/tasks/{ids['task2']}/uncomplete")
        r = c.post(f"/api/v2/student/tasks/{ids['task2']}/complete",
                   json={"correct": 15, "wrong": 3, "blank": 2})
        check("5. complete blank ile → kaydedildi",
              r.status_code == 200 and _blank_of(ids["item2"]) == 2,
              f"{r.status_code} blank={_blank_of(ids['item2'])}")
        r = c.post(f"/api/v2/student/tasks/{ids['task2']}/uncomplete")
        check("6. uncomplete → blank NULL",
              r.status_code == 200 and _blank_of(ids["item2"]) is None,
              str(_blank_of(ids["item2"])))

        # 9-10 (öğrenci tarafında): negatif + sentinel
        r = c.post(f"/api/v2/student/tasks/{ids['task1']}/items/{ids['item1']}/set-completed",
                   json={"completed": 4, "blank": -2})
        check("9. negatif blank → 422", r.status_code == 422, str(r.status_code))
        r = c.post(f"/api/v2/student/tasks/{ids['task1']}/items/{ids['item1']}/set-completed",
                   json={"completed": 4, "correct": 32})
        check("10. blank'sız güncelleme mevcut blank'i KORUR",
              r.status_code == 200 and _blank_of(ids["item1"]) == 4,
              f"{r.status_code} blank={_blank_of(ids['item1'])}")

        # 7-8: koç düzeltir + görür
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login", json={"email": T1, "password": PASSWORD})
        assert r.status_code == 200
        r = c.post(f"/api/v2/teacher/tasks/{ids['task1']}/items/{ids['item1']}/result",
                   json={"completed": 4, "correct": 31, "wrong": 5, "blank": 6})
        check("7. koç /result blank ile → 200 + kaydedildi",
              r.status_code == 200 and _blank_of(ids["item1"]) == 6,
              f"{r.status_code} blank={_blank_of(ids['item1'])}")
        r = c.get(f"/api/v2/teacher/students/{ids['s']}/day?date={ids['today']}")
        item = next(it for t in r.json()["tasks"] if t["id"] == ids["task1"]
                    for it in t["items"])
        check("8. koç gün görünümünde blank_count döner",
              item.get("blank_count") == 6, str(item.get("blank_count")))
    finally:
        _cleanup(ids)

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
