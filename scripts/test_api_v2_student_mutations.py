"""API v2 /student tasks mutations smoke (Dalga 2 Paket 2).

OOB swap karşılığı — MutationResponse.invalidate sözleşmesinin canlı sınavı.

Senaryolar (12):
   1. complete happy path → PENDING → COMPLETED + invalidate listesi 4 madde
   2. complete idempotent → zaten COMPLETED + tekrar 200 (event tetiklenmesin)
   3. complete gelecek tarihli görev → 400 future_task_blocked
   4. complete başkasının görevi → 404 task_not_found
   5. complete kapasite ihlali → 422 RESERVE_OVER_CAPACITY
   6. uncomplete COMPLETED → PENDING (completed_count=0, rezerv iadesi)
   7. uncomplete geçmiş tarihli görev → 200 (gelecek bloğu yok)
   8. items set-completed kısmi → PARTIAL
   9. items set-completed tam → COMPLETED + event
  10. items set-completed sıfırlama → PENDING
  11. items kapasite aşımı (silent clamp) → 200, completed=planned'a düşer
  12. items olmayan item_id → 404 item_not_found

Test verisi: secrets prefix + cleanup; mevcut hesaplara dokunulmaz.
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


PFX = f"v2sm_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_s2@test.invalid"
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
    """Test verisi: 1 öğretmen + 2 öğrenci + 1 kitap (3 section, 30 test).

    Görevler:
      - task_today      → bugün, planned=5, completed=0 (happy path için)
      - task_tomorrow   → yarın, planned=3, completed=0 (future block)
      - task_yesterday  → dün,   planned=2, completed=2 (uncomplete için pre-set)
      - other_task      → diğer öğrenciye ait (başkasınınki testi)
      - task_full_cap   → bugün, planned=3, section'da hiç boşluk yok (RESERVE_OVER_CAPACITY)
    """
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Mut Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Mut Test Öğrenci", role=UserRole.STUDENT, is_active=True,
            grade_level=8,
        )
        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğrenci", role=UserRole.STUDENT, is_active=True,
            grade_level=8,
        )
        db.add_all([teacher, student, other_student])
        db.flush()
        student.teacher_id = teacher.id
        other_student.teacher_id = teacher.id

        subj = Subject(name=f"V2Mut Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()

        book = Book(
            name=f"V2Mut Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()

        # 3 section × test_count = farklı
        sec_a = BookSection(book_id=book.id, label="Bölüm A", test_count=10, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="Bölüm B", test_count=10, order=1, topic_id=topic.id)
        # sec_c FULL-CAP testi: test_count=2 + sp_c(0/0) → planned=3 complete edilemez
        # (needed_reserve = 3 - 0 = 3; 0+0+3=3 > test_count=2 → ReservationError)
        sec_c = BookSection(book_id=book.id, label="Bölüm C", test_count=2, order=2, topic_id=topic.id)
        db.add_all([sec_a, sec_b, sec_c]); db.flush()

        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()

        # Önceki run yetimleri sil (SQLite PK reuse koruması)
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == sb.id))
        db.flush()

        # SectionProgress'ler
        sp_a = SectionProgress(student_book_id=sb.id, book_section_id=sec_a.id,
                               completed_count=0, reserved_count=5)
        sp_b = SectionProgress(student_book_id=sb.id, book_section_id=sec_b.id,
                               completed_count=2, reserved_count=2)
        # sec_c: hiç rezerv yok ama test_count=2 → planned=3 complete bekleyenin
        # rezerv açma denemesi capacity'yi (2) aşacak → ReservationError.
        sp_c = SectionProgress(student_book_id=sb.id, book_section_id=sec_c.id,
                               completed_count=0, reserved_count=0)
        db.add_all([sp_a, sp_b, sp_c]); db.flush()

        today = date.today()
        # task_today — sec_a, planned=5 (sp_a.reserved=5 ile birebir uyumlu)
        task_today = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Bugünkü test görevi", status=TaskStatus.PENDING, order=0,
        )
        db.add(task_today); db.flush()
        item_today = TaskBookItem(
            task_id=task_today.id, book_id=book.id, book_section_id=sec_a.id,
            planned_count=5, completed_count=0,
        )
        db.add(item_today); db.flush()

        # task_tomorrow — gelecek tarihli (future block)
        task_tomorrow = Task(
            student_id=student.id, date=today + timedelta(days=1), type=TaskType.TEST,
            title="Yarınki görev", status=TaskStatus.PENDING, order=0,
        )
        db.add(task_tomorrow); db.flush()
        item_tomorrow = TaskBookItem(
            task_id=task_tomorrow.id, book_id=book.id, book_section_id=sec_b.id,
            planned_count=3, completed_count=0,
        )
        db.add(item_tomorrow); db.flush()

        # task_yesterday — dün, ZATEN COMPLETED (uncomplete için)
        task_yesterday = Task(
            student_id=student.id, date=today - timedelta(days=1), type=TaskType.TEST,
            title="Dünkü tamamlanmış", status=TaskStatus.COMPLETED, order=0,
        )
        db.add(task_yesterday); db.flush()
        item_yesterday = TaskBookItem(
            task_id=task_yesterday.id, book_id=book.id, book_section_id=sec_b.id,
            planned_count=2, completed_count=2,    # sp_b.completed=2 bunu yansıtır
        )
        db.add(item_yesterday); db.flush()

        # other_student'a ait görev — sahiplik testi için
        other_task = Task(
            student_id=other_student.id, date=today, type=TaskType.TEST,
            title="Diğer öğrencinin görevi", status=TaskStatus.PENDING, order=0,
        )
        db.add(other_task); db.flush()

        # task_full_cap — sec_c (test_count=2) hedefliyor, item planned=3.
        # complete_task çağrısında: to_complete=3, needed_reserve=3-0=3,
        # check 0+0+3=3 > 2 → ReservationError → endpoint 422 döner.
        task_full_cap = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Kapasite dolu görev", status=TaskStatus.PENDING, order=1,
        )
        db.add(task_full_cap); db.flush()
        item_full_cap = TaskBookItem(
            task_id=task_full_cap.id, book_id=book.id, book_section_id=sec_c.id,
            planned_count=3, completed_count=0,
        )
        db.add(item_full_cap); db.flush()

        db.commit()
        return {
            "teacher_id": teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "subject_id": subj.id,
            "topic_id": topic.id,
            "book_id": book.id,
            "sb_id": sb.id,
            "sec_ids": [sec_a.id, sec_b.id, sec_c.id],
            "sp_ids": [sp_a.id, sp_b.id, sp_c.id],
            "task_today_id": task_today.id,
            "item_today_id": item_today.id,
            "task_tomorrow_id": task_tomorrow.id,
            "task_yesterday_id": task_yesterday.id,
            "other_task_id": other_task.id,
            "task_full_cap_id": task_full_cap.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        task_ids = [
            seed["task_today_id"], seed["task_tomorrow_id"],
            seed["task_yesterday_id"], seed["other_task_id"],
            seed["task_full_cap_id"],
        ]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
        db.execute(sa_delete(Task).where(Task.id.in_(task_ids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == seed["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == seed["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.id.in_(seed["sec_ids"])))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["other_student_id"], seed["teacher_id"],
        ])))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /student mutations smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded student={seed['student_id']} task_today={seed['task_today_id']}\n")

    try:
        client = TestClient(app)
        _login_v2(client, STUDENT_EMAIL)

        # ===== 1. complete happy path =====
        r = client.post(f"/api/v2/student/tasks/{seed['task_today_id']}/complete")
        body = r.json() if r.text else {}
        invalidate = body.get("invalidate", [])
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("status") == "completed"
            and data.get("completed_count") == 5
            and len(invalidate) == 4
            and any("day:" in k for k in invalidate)
            and any(":sidebar" in k for k in invalidate)
            and any(":summary:" in k for k in invalidate)
            and any("badges:" in k for k in invalidate)
        )
        check(
            "1. complete happy path",
            ok,
            f"status={r.status_code} task_status={data.get('status')} invalidate={invalidate}",
        )

        # ===== 2. complete idempotent (zaten COMPLETED) =====
        r = client.post(f"/api/v2/student/tasks/{seed['task_today_id']}/complete")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("status") == "completed"
            and body.get("data", {}).get("completed_count") == 5
        )
        check(
            "2. complete idempotent",
            ok,
            f"status={r.status_code} body={r.text[:160]}",
        )

        # ===== 3. complete gelecek tarihli → 400 future_task_blocked =====
        r = client.post(f"/api/v2/student/tasks/{seed['task_tomorrow_id']}/complete")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 400
            and body.get("detail", {}).get("code") == "future_task_blocked"
        )
        check(
            "3. complete future → 400",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 4. complete başkasının görevi → 404 =====
        r = client.post(f"/api/v2/student/tasks/{seed['other_task_id']}/complete")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "task_not_found"
        )
        check(
            "4. complete başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 5. complete kapasite ihlali → 422 RESERVE_OVER_CAPACITY =====
        r = client.post(f"/api/v2/student/tasks/{seed['task_full_cap_id']}/complete")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "RESERVE_OVER_CAPACITY"
        )
        check(
            "5. complete kapasite → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 6. uncomplete COMPLETED → PENDING =====
        r = client.post(f"/api/v2/student/tasks/{seed['task_yesterday_id']}/uncomplete")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("status") == "pending"
            and data.get("completed_count") == 0
            and len(body.get("invalidate", [])) == 4
        )
        check(
            "6. uncomplete COMPLETED → PENDING",
            ok,
            f"status={r.status_code} task_status={data.get('status')} completed={data.get('completed_count')}",
        )

        # ===== 7. uncomplete geçmiş tarihli görev → 200 (gelecek bloğu yok) =====
        # 1. step'te tamamladığımız task_today_id'yi şimdi geri al; geçmiş değil ama
        # uncomplete future bloğu kontrol etmez → 200 dönmeli.
        r = client.post(f"/api/v2/student/tasks/{seed['task_today_id']}/uncomplete")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("status") == "pending"
        )
        check(
            "7. uncomplete bugünkü → 200",
            ok,
            f"status={r.status_code} body={r.text[:160]}",
        )

        # ===== 8. items set-completed kısmi → PARTIAL =====
        # task_today_id now PENDING (just uncompleted). item planned=5. Set 2.
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_today_id']}/items/{seed['item_today_id']}/set-completed",
            json={"completed": 2},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("status") == "partial"
            and data.get("completed_count") == 2
        )
        check(
            "8. items partial → PARTIAL",
            ok,
            f"status={r.status_code} task_status={data.get('status')} completed={data.get('completed_count')}",
        )

        # ===== 9. items set-completed tam → COMPLETED =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_today_id']}/items/{seed['item_today_id']}/set-completed",
            json={"completed": 5},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("status") == "completed"
            and data.get("completed_count") == 5
        )
        check(
            "9. items full → COMPLETED",
            ok,
            f"status={r.status_code} task_status={data.get('status')}",
        )

        # ===== 10. items set-completed sıfırlama → PENDING =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_today_id']}/items/{seed['item_today_id']}/set-completed",
            json={"completed": 0},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("status") == "pending"
            and data.get("completed_count") == 0
        )
        check(
            "10. items zero → PENDING",
            ok,
            f"status={r.status_code} task_status={data.get('status')}",
        )

        # ===== 11. items kapasite aşımı → silent clamp (200, completed=planned) =====
        # Service `new_completed > planned_count` durumunda planned_count'a klampler.
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_today_id']}/items/{seed['item_today_id']}/set-completed",
            json={"completed": 999},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        # Service klamp: completed = planned_count (5)
        ok = (
            r.status_code == 200
            and data.get("completed_count") == 5      # clamp to planned
            and data.get("status") == "completed"
        )
        check(
            "11. items over-clamp → planned tavanına klamp",
            ok,
            f"status={r.status_code} completed={data.get('completed_count')}",
        )

        # ===== 12. items olmayan item_id → 404 item_not_found =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_today_id']}/items/9999999/set-completed",
            json={"completed": 1},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "item_not_found"
        )
        check(
            "12. items olmayan id → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

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
