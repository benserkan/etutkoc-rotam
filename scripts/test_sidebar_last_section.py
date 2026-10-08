"""Kaynak Durumu "kaldığı yer" — kitapta en son görev verilen ünite (2026-10-08).

Koç: "bir bakışta bu kitapta hangi konuda kalındığı, en son hangi görevin
verildiği anlaşılmıyor". Kitap sırası sık atlandığı için kaldığı yer SIRADAN
değil son görevden çıkarılır.

Senaryolar:
  1. Son görev verilen ünite kitap sırasında ortada olsa da doğru seçilir
  2. Ünite başına son görev tarihi döner; görevsiz ünitede None
  3. Aynı tarihte iki ünite → daha yeni (sonra oluşturulan) görev kazanır
  4. Hiç görevi olmayan kitapta last_* None
  5. Başka öğrencinin görevi bu öğrencinin "son"unu etkilemez
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    SuspiciousIp, Task, TaskBookItem, TaskType, User, UserRole,
)
from app.services.security import hash_password

PFX = f"sls_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


def check(name, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def _task(db, st, book, sec, day):
    t = Task(student_id=st.id, date=day, type=TaskType.TEST, title="g", is_draft=False)
    db.add(t)
    db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id, planned_count=1))
    return t


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Sls Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Sls Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD),
                     full_name="Sls Diğer", role=UserRole.STUDENT, is_active=True,
                     teacher_id=coach.id, grade_level=12)
        db.add_all([st, other])
        db.flush()
        subj = Subject(name=f"Sls Fizik {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        b1 = Book(name=f"Sls Kitap1 {PFX}", subject_id=subj.id, teacher_id=coach.id,
                  type=BookType.SORU_BANKASI)
        b2 = Book(name=f"Sls Kitap2 {PFX}", subject_id=subj.id, teacher_id=coach.id,
                  type=BookType.SORU_BANKASI)
        b3 = Book(name=f"Sls Kitap3 {PFX}", subject_id=subj.id, teacher_id=coach.id,
                  type=BookType.SORU_BANKASI)
        db.add_all([b1, b2, b3])
        db.flush()
        secs = {}
        for b in (b1, b2, b3):
            for i, lab in enumerate(("Hareket", "Kuvvet", "Basınç", "Kaldırma Kuvveti")):
                sec = BookSection(book_id=b.id, label=lab, test_count=10, order=i)
                db.add(sec)
                db.flush()
                secs[(b.id, lab)] = sec
        sbs = []
        for b in (b1, b2, b3):
            sb = StudentBook(student_id=st.id, book_id=b.id)
            db.add(sb)
            db.flush()
            sbs.append(sb.id)
        sb_o = StudentBook(student_id=other.id, book_id=b1.id)
        db.add(sb_o)
        db.flush()
        sbs.append(sb_o.id)
        # Kitap1: Hareket (d-10) · Kaldırma Kuvveti (d-3) · Basınç (d-1) → son = Basınç
        _task(db, st, b1, secs[(b1.id, "Hareket")], today - timedelta(days=10))
        _task(db, st, b1, secs[(b1.id, "Kaldırma Kuvveti")], today - timedelta(days=3))
        _task(db, st, b1, secs[(b1.id, "Basınç")], today - timedelta(days=1))
        # Diğer öğrenci kitap1'de daha yeni görev → etkilememeli
        _task(db, other, b1, secs[(b1.id, "Kuvvet")], today + timedelta(days=2))
        # Kitap2: aynı gün Kuvvet sonra Hareket → Hareket (daha yeni görev)
        _task(db, st, b2, secs[(b2.id, "Kuvvet")], today)
        _task(db, st, b2, secs[(b2.id, "Hareket")], today)
        db.commit()
        return {"coach": coach.id, "student": st.id, "other": other.id, "subject": subj.id,
                "books": [b1.id, b2.id, b3.id], "sbs": sbs,
                "secs": {f"{k[0]}:{k[1]}": v.id for k, v in secs.items()},
                "today": today}


def cleanup(s):
    with SessionLocal() as db:
        uid = [s["coach"], s["student"], s["other"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uid)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(s["sbs"])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(s["sbs"])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(s["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(s["books"])))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()


def main() -> int:
    s = seed()
    print(f"\n=== Kaynak Durumu kaldığı yer smoke (öğrenci #{s['student']}) ===\n")
    try:
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get(f"/api/v2/teacher/students/{s['student']}/sidebar-items")
        assert r.status_code == 200, r.text
        books = {b["id"]: b for sub in r.json()["subjects"] for b in sub["books"]}
        b1, b2, b3 = (books[i] for i in s["books"])
        t = s["today"]

        check("1. kitap1: son görev = Basınç (sırada ortada olsa da)",
              b1["last_section_label"] == "Basınç"
              and b1["last_section_id"] == s["secs"][f"{s['books'][0]}:Basınç"]
              and b1["last_task_date"] == (t - timedelta(days=1)).isoformat(), str(b1)[:300])
        dates = {x["label"]: x["last_task_date"] for x in b1["sections"]}
        check("2. ünite başına son görev tarihi; görevsizde None",
              dates["Hareket"] == (t - timedelta(days=10)).isoformat()
              and dates["Kaldırma Kuvveti"] == (t - timedelta(days=3)).isoformat()
              and dates["Kuvvet"] is None, str(dates))
        check("3. aynı tarih → daha yeni görev (Hareket) kazanır",
              b2["last_section_label"] == "Hareket", str(b2.get("last_section_label")))
        check("4. görevsiz kitapta last_* None",
              b3["last_section_id"] is None and b3["last_section_label"] is None
              and b3["last_task_date"] is None)
        check("5. başka öğrencinin daha yeni görevi etkilemez (Kuvvet seçilmedi)",
              b1["last_section_label"] != "Kuvvet")
    finally:
        cleanup(s)
    print(f"\n{passed} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
