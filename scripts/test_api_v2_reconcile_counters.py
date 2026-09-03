"""Sayaç onarımı ucu smoke (2026-09-03 saha vakası).

Saha: "345 TYT Fizik · İş, Güç ve Enerji" bölümünde kayıtlı rezerv 3 iken
gerçek görevlerin tamamı COMPLETED'dı → ölü rezerv takılı kaldığı için koç o
bölüme yeni test atayamıyordu ("rezerv kaldıramıyorum") ve onarımın UI'da
karşılığı yoktu (yalnız SSH script'i).

Senaryolar:
  1. Ölü rezerv (tamamlanmış görevler + şişik sayaç) → uç düzeltir, rezerv 0
  2. İdempotent: ikinci çağrı fixed=0
  3. Kapasite geri döner: onarımdan sonra bölüme yeni görev atanabilir
  4. Baseline KORUNUR: kayıtlı completed, kalem toplamından büyükse düşürülmez
  5. Aktif (tamamlanmamış) görevin rezervi KORUNUR — onarım canlı planı bozmaz
  6. Sahiplik: başka koçun öğrencisi → 404 · atanmamış kitap → 404
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

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
    SuspiciousIp,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.security import hash_password

PFX = f"rec_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Rec Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Rec Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Rec Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=11)
        st2 = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWD),
                   full_name="Rec Öğrenci2", role=UserRole.STUDENT, is_active=True,
                   teacher_id=other.id, grade_level=11)
        db.add_all([st, st2])
        db.flush()
        subj = Subject(name=f"Rec Ders {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"Rec Kitap {PFX}", subject_id=subj.id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        s_dead = BookSection(book_id=book.id, label="Ölü Rezerv Bölümü",
                             test_count=22, order=1)
        s_live = BookSection(book_id=book.id, label="Canlı Bölüm",
                             test_count=10, order=2)
        s_base = BookSection(book_id=book.id, label="Baseline Bölümü",
                             test_count=10, order=3)
        db.add_all([s_dead, s_live, s_base])
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()

        # (1) ölü rezerv: 5 görev, hepsi COMPLETED (15 test) ama sayaç rezerv 3
        for i in range(5):
            t = Task(student_id=st.id, date=today - timedelta(days=30 + i),
                     type=TaskType.TEST, title="Bitmiş görev",
                     status=TaskStatus.COMPLETED, is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=s_dead.id,
                                planned_count=3, completed_count=3))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s_dead.id,
                               reserved_count=3, completed_count=19))

        # (5) canlı görev: tamamlanmamış → rezervi KORUNMALI
        t_live = Task(student_id=st.id, date=today + timedelta(days=1),
                      type=TaskType.TEST, title="Aktif görev",
                      status=TaskStatus.PENDING, is_draft=False)
        db.add(t_live)
        db.flush()
        db.add(TaskBookItem(task_id=t_live.id, book_id=book.id,
                            book_section_id=s_live.id,
                            planned_count=4, completed_count=0))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s_live.id,
                               reserved_count=4, completed_count=0))

        # (4) baseline: görev kalemi YOK ama koç "zaten çözmüştü" demiş
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s_base.id,
                               reserved_count=0, completed_count=6))
        db.commit()
        return {
            "coach_id": coach.id, "other_id": other.id, "student_id": st.id,
            "student2_id": st2.id, "book_id": book.id, "subject_id": subj.id,
            "sb_id": sb.id, "s_dead": s_dead.id, "s_live": s_live.id,
            "s_base": s_base.id,
        }


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["other_id"], s["student_id"], s["student2_id"]]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id == s["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == s["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == s["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == s["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def counters(sb_id: int, sec_id: int) -> tuple[int, int]:
    with SessionLocal() as db:
        sp = (db.query(SectionProgress)
              .filter(SectionProgress.student_book_id == sb_id,
                      SectionProgress.book_section_id == sec_id).first())
        return (sp.reserved_count, sp.completed_count) if sp else (-1, -1)


def main() -> int:
    s = seed()
    sid, bid = s["student_id"], s["book_id"]
    print(f"\n=== Sayaç onarımı smoke (öğrenci #{sid}) ===\n")
    try:
        c = TestClient(app)
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        url = f"/api/v2/teacher/students/{sid}/books/{bid}/reconcile-counters"

        before = counters(s["sb_id"], s["s_dead"])
        r = c.post(url)
        body = r.json() if r.text else {}
        after = counters(s["sb_id"], s["s_dead"])
        check("1. ölü rezerv temizlendi (3 → 0)",
              r.status_code == 200 and before[0] == 3 and after[0] == 0,
              f"status={r.status_code} önce={before} sonra={after}")

        check("2. yanıt düzeltilen bölümü raporluyor",
              (body.get("data", {}).get("fixed") or 0) >= 1,
              f"data={body.get('data')}")

        r2 = c.post(url)
        check("3. idempotent — ikinci çağrı fixed=0",
              r2.status_code == 200 and r2.json()["data"]["fixed"] == 0,
              f"{r2.json().get('data')}")

        live = counters(s["sb_id"], s["s_live"])
        check("4. AKTİF görevin rezervi korundu (4)", live[0] == 4, f"{live}")

        base = counters(s["sb_id"], s["s_base"])
        check("5. baseline 'zaten çözmüştü' korundu (completed 6)",
              base[1] == 6, f"{base}")

        # 6. kapasite geri döndü mü → bölüme yeni görev atanabilmeli
        r3 = c.post(
            f"/api/v2/teacher/students/{sid}/tasks",
            json={"date": date.today().isoformat(), "type": "test",
                  "title": "Onarım sonrası", "is_draft": False,
                  "items": [{"book_id": bid, "section_id": s["s_dead"],
                             "planned_count": 3}]},
        )
        check("6. onarımdan sonra bölüme yeni test atanabiliyor",
              r3.status_code == 200, f"status={r3.status_code} {r3.text[:160]}")

        # 7. sahiplik
        r4 = c.post(
            f"/api/v2/teacher/students/{s['student2_id']}/books/{bid}/reconcile-counters")
        r5 = c.post(f"/api/v2/teacher/students/{sid}/books/999999/reconcile-counters")
        check("7. yabancı öğrenci 404 + atanmamış kitap 404",
              r4.status_code == 404 and r5.status_code == 404,
              f"{r4.status_code}/{r5.status_code}")
    finally:
        cleanup(s)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    if failed:
        for f in failed:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
