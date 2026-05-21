"""API v2 /student/* salt okunur smoke (Dalga 2 Paket 1).

Senaryolar (10):
   1. /api/v2/student/day bugün (cookie login) → 200, tasks listesi
   2. /api/v2/student/day belirli tarih → 200
   3. /api/v2/student/day yarın → 200, is_future=true, can_request.add=true
   4. /api/v2/student/day geçersiz tarih → 422 invalid_date
   5. /api/v2/student/day TEACHER kullanıcısıyla → 403 role_required
   6. /api/v2/student/day auth yok → 401 missing_credentials
   7. /api/v2/student/week varsayılan start → 200, 7 gün, total pct
   8. /api/v2/student/books → 200, subjects listesi + sidebar totals
   9. /api/v2/student/book-grid kendi kitabı → 200, sections + cells
  10. /api/v2/student/book-grid olmayan/başkasının kitabı → 404 book_not_assigned
  11. /api/v2/student/badges → 200, pending_count=int

Test verisi: secrets prefix ile teacher + student + subject + book + section +
StudentBook + Task (bugün) + TaskBookItem. Mevcut hesaplara dokunulmaz.
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

from app.config import settings
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
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2sr_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
OTHER_BOOK_NAME = f"BAŞKASI {PFX}"
PASSWORD = "TestPass123!@xyz"

ACCESS = settings.auth_cookie_access_name

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
    """Test verisi kur: teacher + student + book + section + task + diğer öğretmen kitabı."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Stud Read Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Stud Read Öğrenci", role=UserRole.STUDENT, is_active=True,
            grade_level=8,
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        db.add_all([teacher, student, other_teacher])
        db.flush()
        student.teacher_id = teacher.id

        # Built-in olmayan subject + topic (test silmek kolay olsun diye)
        subj = Subject(name=f"Test Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()

        # Test kitabı 50 test, 1 section
        book = Book(
            name=f"Test Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()
        sec = BookSection(
            book_id=book.id, label="Bölüm 1", test_count=50, order=0, topic_id=topic.id,
        )
        db.add(sec); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()

        # SQLite PK reuse + FK CASCADE eksikliği → önceki test run'larından yetim
        # SectionProgress kalabilir. Bizim yeni sb.id'mize bağlı olabilecek yetimleri sil.
        from sqlalchemy import delete as sa_delete
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == sb.id))
        db.flush()

        # Mevcut completed/reserved progress'i ekle (analytics için)
        sp = SectionProgress(
            student_book_id=sb.id, book_section_id=sec.id,
            completed_count=3, reserved_count=5,
        )
        db.add(sp); db.flush()

        # Bugünkü görev: 5 planlı, 0 tamam (rezerv'in 5'i bu task)
        task = Task(
            student_id=student.id, date=date.today(), type=TaskType.TEST,
            title="API v2 test görevi", status=TaskStatus.PENDING, order=0,
        )
        db.add(task); db.flush()
        item = TaskBookItem(
            task_id=task.id, book_id=book.id, book_section_id=sec.id,
            planned_count=5, completed_count=0,
        )
        db.add(item); db.flush()

        # Başka öğretmenin kitabı (öğrenciye atanmamış) — 404 testi için
        other_book = Book(
            name=OTHER_BOOK_NAME, subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=other_teacher.id,
        )
        db.add(other_book); db.flush()

        db.commit()
        return {
            "teacher_id": teacher.id,
            "student_id": student.id,
            "other_teacher_id": other_teacher.id,
            "book_id": book.id,
            "other_book_id": other_book.id,
            "task_id": task.id,
            "subject_id": subj.id,
            "topic_id": topic.id,
            "sec_id": sec.id,
            "sb_id": sb.id,
            "sp_id": sp.id,
            "item_id": item.id,
        }


def _cleanup(seed: dict) -> None:
    from sqlalchemy import delete as sa_delete
    with SessionLocal() as db:
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id == seed["task_id"]))
        db.execute(sa_delete(Task).where(Task.student_id == seed["student_id"]))
        # Bu sb'ye bağlı TÜM SP'leri sil (yalnız bizim eklediğimizi değil; SQLite PK
        # reuse durumunda yetim de kalmasın — gelecekteki testler temiz başlasın).
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == seed["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == seed["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.id == seed["sec_id"]))
        db.execute(sa_delete(Book).where(Book.id.in_([seed["book_id"], seed["other_book_id"]])))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["teacher_id"], seed["other_teacher_id"],
        ])))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    """v2 cookie login ile client'a cookie kur (sonraki istekler taşır)."""
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /student/* salt okunur smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded: student={seed['student_id']} book={seed['book_id']} task={seed['task_id']}\n")

    try:
        # ===== 1. /day bugün =====
        client = TestClient(app)
        _login_v2(client, STUDENT_EMAIL)
        r = client.get("/api/v2/student/day")
        body = r.json() if r.text else {}
        sb = body.get("sidebar", {}) if isinstance(body, dict) else {}
        cr = body.get("can_request", {}) if isinstance(body, dict) else {}
        first_task = body.get("tasks", [{}])[0] if body.get("tasks") else {}
        ok = (
            r.status_code == 200
            and body.get("date") == date.today().isoformat()
            and body.get("is_today") is True
            and isinstance(body.get("tasks"), list)
            and len(body["tasks"]) == 1
            and first_task.get("planned_count") == 5
            and first_task.get("is_future_blocked") is False
            and isinstance(sb, dict)
            and sb.get("total_tests") == 50
            and sb.get("completed_tests") == 3
            and sb.get("reserved_tests") == 5
            and cr.get("question") is True
        )
        check(
            "1. /day bugün",
            ok,
            f"status={r.status_code} "
            f"date={body.get('date')} is_today={body.get('is_today')} "
            f"tasks_len={len(body.get('tasks', []))} "
            f"task_planned={first_task.get('planned_count')} "
            f"task_future_blocked={first_task.get('is_future_blocked')} "
            f"sidebar_total={sb.get('total_tests')} sidebar_done={sb.get('completed_tests')} "
            f"sidebar_res={sb.get('reserved_tests')} can_question={cr.get('question')}",
        )

        # ===== 2. /day belirli tarih (dün) =====
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        r = client.get(f"/api/v2/student/day?date={yesterday}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("date") == yesterday
            and body.get("is_past") is True
            and body.get("is_future") is False
        )
        check("2. /day belirli tarih (dün)", ok,
              f"status={r.status_code} is_past={body.get('is_past')}")

        # ===== 3. /day yarın → is_future=true =====
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.get(f"/api/v2/student/day?date={tomorrow}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("is_future") is True
            and body.get("can_request", {}).get("add") is True
        )
        check("3. /day yarın is_future + can_add", ok,
              f"status={r.status_code} future={body.get('is_future')}")

        # ===== 4. /day geçersiz tarih =====
        r = client.get("/api/v2/student/day?date=NOT-A-DATE")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "invalid_date"
        )
        check("4. /day invalid date → 422", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 5. /day TEACHER kullanıcısıyla → 403 =====
        teacher_client = TestClient(app)
        _login_v2(teacher_client, TEACHER_EMAIL)
        r = teacher_client.get("/api/v2/student/day")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 403
            and body.get("detail", {}).get("code") == "role_required"
        )
        check("5. /day TEACHER → 403", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 6. /day auth yok → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/student/day")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 401
            and body.get("detail", {}).get("code") == "missing_credentials"
        )
        check("6. /day anon → 401", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 7. /week varsayılan → 7 gün =====
        r = client.get("/api/v2/student/week")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and isinstance(body.get("days"), list)
            and len(body["days"]) == 7
            and body["days"][0]["date"] == date.today().isoformat()
            and "total_planned" in body
            and "total_pct" in body
        )
        check("7. /week 7 gün", ok,
              f"status={r.status_code} days_len={len(body.get('days', []))}")

        # ===== 8. /books → 200 =====
        r = client.get("/api/v2/student/books")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("total_tests") == 50
            and isinstance(body.get("subjects"), list)
            and len(body["subjects"]) >= 1
            and len(body["subjects"][0].get("books", [])) >= 1
            and body["subjects"][0]["books"][0]["book_name"].startswith("Test Kitap")
        )
        check("8. /books envanter", ok,
              f"status={r.status_code} subjects={len(body.get('subjects', []))}")

        # ===== 9. /book-grid kendi kitabı =====
        r = client.get(f"/api/v2/student/book-grid?book_id={seed['book_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("book_id") == seed["book_id"]
            and isinstance(body.get("sections"), list)
            and len(body["sections"]) == 1
            and body["sections"][0]["test_count"] == 50
            and isinstance(body["sections"][0].get("cells"), list)
            and len(body["sections"][0]["cells"]) == 50    # tüm test_count cells
            and body["total_completed"] == 3
            and body["total_reserved"] == 5
        )
        check("9. /book-grid kendi kitap", ok,
              f"status={r.status_code} cells_len={len(body.get('sections', [{}])[0].get('cells', []))}")

        # ===== 10. /book-grid başkasının kitabı → 404 =====
        r = client.get(f"/api/v2/student/book-grid?book_id={seed['other_book_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "book_not_assigned"
        )
        check("10. /book-grid başkası → 404", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 11. /badges → 200, pending_count=int =====
        r = client.get("/api/v2/student/badges")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and isinstance(body.get("pending_count"), int)
            and "checked_at" in body
        )
        check("11. /badges polling", ok,
              f"status={r.status_code} body={r.text[:160]}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()
        print("\n  cleanup OK\n")

    total = passed + len(failed)
    print(f"\n=== SONUÇ: {passed}/{total} PASS ===")
    if failed:
        print("\nFAILED:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
