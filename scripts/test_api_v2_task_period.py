"""M6 — Görev periyodu (sabah/öğle/akşam) smoke.

Senaryolar (10):
   1. POST + period=morning → 200, serialize'da period=morning
   2. POST + period=null (default) → 200, period=None
   3. POST + period=invalid → 422 invalid_period
   4. PATCH + period=evening → 200, güncel
   5. PATCH + period="" (boş string) → period=NULL (temizle)
   6. PATCH + period=invalid → 422
   7. Öğrenci /day görünümünde period serialize edilir
   8. POST geçersiz hour + valid period → invalid_hour 422 (period sırasına gelmedi)
   9. period case-insensitive normalize ("Morning" → "morning")
  10. period None (kasıtlı) → kalır None
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
    SuspiciousIp,
    Task,
    TaskBookItem,
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2pe_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
PASSWORD = "TestPass123!@xyz"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Period Test Öğretmen", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Period Test Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id

        subj = Subject(name=f"Period Ders {PFX}", order=999, is_builtin=False,
                       teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()
        book = Book(name=f"Period Kitap {PFX}", subject_id=subj.id,
                    type=BookType.SORU_BANKASI, teacher_id=teacher.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="A", test_count=50,
                          order=0, topic_id=topic.id)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == sb.id))
        sp = SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                             completed_count=0, reserved_count=0)
        db.add(sp); db.flush()

        db.commit()
        return {
            "teacher_id": teacher.id,
            "student_id": student.id,
            "subject_id": subj.id,
            "topic_id": topic.id,
            "book_id": book.id,
            "section_id": sec.id,
            "sb_id": sb.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        # Tüm seed öğrenci görevlerini sil
        task_ids = [tid for (tid,) in db.query(Task.id).filter(Task.student_id == seed["student_id"]).all()]
        if task_ids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
            db.execute(sa_delete(Task).where(Task.id.in_(task_ids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == seed["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == seed["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.id == seed["section_id"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["teacher_id"],
        ])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def _create_task(client, seed: dict, *, period=None, hour=None,
                 extra: dict | None = None) -> tuple[int, dict, dict]:
    body = {
        "date": date.today().isoformat(),
        "type": "test",
        "title": "Period test",
        "scheduled_hour": hour,
        "items": [{
            "book_id": seed["book_id"],
            "section_id": seed["section_id"],
            "planned_count": 3,
        }],
    }
    if period is not None:
        body["period"] = period
    if extra:
        body.update(extra)
    r = client.post(
        f"/api/v2/teacher/students/{seed['student_id']}/tasks",
        json=body,
    )
    j = r.json() if r.text else {}
    return r.status_code, j, body


def main() -> int:
    print(f"\n=== M6 görev periyot smoke — prefix: {PFX} ===\n")
    seed = _seed()

    try:
        client = TestClient(app)
        _login(client, TEACHER_EMAIL)

        # ===== 1. POST + period=morning =====
        sc, j, _ = _create_task(client, seed, period="morning")
        data = j.get("data", {})
        task_morning_id = data.get("id")
        ok = sc == 200 and data.get("period") == "morning"
        check("1. POST + period=morning → 200",
              ok, f"status={sc} period={data.get('period')}")

        # ===== 2. POST + period=null (default) =====
        sc, j, _ = _create_task(client, seed)  # period geçirme
        ok = sc == 200 and j.get("data", {}).get("period") is None
        check("2. POST + period yok → null",
              ok, f"status={sc} period={j.get('data', {}).get('period')}")

        # ===== 3. POST + period=invalid → 422 =====
        sc, j, _ = _create_task(client, seed, period="midnight")
        ok = (sc == 422
              and j.get("detail", {}).get("code") == "invalid_period")
        check("3. POST + period=midnight → 422 invalid_period",
              ok, f"status={sc} body={str(j)[:160]}")

        # ===== 4. PATCH + period=evening =====
        r = client.patch(
            f"/api/v2/teacher/tasks/{task_morning_id}",
            json={"period": "evening"},
        )
        ok = r.status_code == 200 and r.json().get("data", {}).get("period") == "evening"
        check("4. PATCH + period=evening → 200",
              ok, f"status={r.status_code}")

        # ===== 5. PATCH + period="" (boş string) → NULL =====
        r = client.patch(
            f"/api/v2/teacher/tasks/{task_morning_id}",
            json={"period": ""},
        )
        ok = r.status_code == 200 and r.json().get("data", {}).get("period") is None
        check("5. PATCH + period='' → NULL (temizle)",
              ok, f"status={r.status_code}")

        # ===== 6. PATCH + period=invalid → 422 =====
        r = client.patch(
            f"/api/v2/teacher/tasks/{task_morning_id}",
            json={"period": "afternoon"},
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 422
              and body.get("detail", {}).get("code") == "invalid_period")
        check("6. PATCH + period=invalid → 422",
              ok, f"status={r.status_code}")

        # ===== 7. Öğrenci /day serialize period =====
        # Önce görev period=noon yap
        client.patch(
            f"/api/v2/teacher/tasks/{task_morning_id}",
            json={"period": "noon"},
        )
        client.post("/api/v2/auth/logout")
        get_login_limiter().reset()
        student_client = TestClient(app)
        student_client.post(
            "/api/v2/auth/login",
            json={"email": STUDENT_EMAIL, "password": PASSWORD},
        )
        r = student_client.get(f"/api/v2/student/day?date={date.today().isoformat()}")
        rows = r.json().get("tasks", []) if r.status_code == 200 else []
        # task_morning_id'nin period'unu bul
        found = next((t for t in rows if t.get("id") == task_morning_id), None)
        ok = r.status_code == 200 and found is not None and found.get("period") == "noon"
        check("7. Öğrenci /day serialize'da period=noon",
              ok, f"status={r.status_code} found={found.get('period') if found else None}")

        # Tekrar koç oturumu
        _login(client, TEACHER_EMAIL)

        # ===== 8. POST geçersiz hour → invalid_hour (period validation öncesi değil) =====
        sc, j, _ = _create_task(client, seed, hour=25, period="morning")
        ok = (sc == 422
              and j.get("detail", {}).get("code") == "invalid_hour")
        check("8. POST hour=25 + period=morning → invalid_hour 422",
              ok, f"status={sc} body={str(j)[:160]}")

        # ===== 9. case-insensitive normalize =====
        sc, j, _ = _create_task(client, seed, period="Morning")
        ok = sc == 200 and j.get("data", {}).get("period") == "morning"
        check("9. period=Morning → normalize 'morning'",
              ok, f"status={sc} period={j.get('data', {}).get('period')}")

        # ===== 10. period=None geçilse de NULL kalır =====
        sc, j, _ = _create_task(client, seed, period=None)
        ok = sc == 200 and j.get("data", {}).get("period") is None
        check("10. period=None → NULL kalır",
              ok, f"status={sc} period={j.get('data', {}).get('period')}")

    finally:
        _cleanup(seed)

    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} geçti ===\n")
    if failed:
        print("Başarısız senaryolar:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
