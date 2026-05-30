"""API v2 görev sonucu (D/Y) smoke — öğrenci + koç akışı.

Senaryolar (12):
   1. öğrenci complete + D/Y boş → tamamla, D/Y null kalır
   2. öğrenci complete + D/Y dolu (tek kalem) → set, serialize'da görünür
   3. öğrenci complete + D/Y invalid (c+w > completed) → 422 invalid_result_distribution
   4. öğrenci set-completed + D/Y boş → completed set, D/Y null
   5. öğrenci set-completed + D/Y dolu → ikisi set, döner
   6. öğrenci set-completed completed=0 → D/Y otomatik null
   7. öğrenci set-completed D/Y negatif → 422
   8. öğrenci uncomplete → D/Y null'a düşer
   9. koç POST /teacher/.../items/{id}/result + D/Y → set
  10. koç result invalid (c+w > completed) → 422
  11. koç result başkasının görevi → 404 task_not_found
  12. koç result olmayan item_id → 404 item_not_found

Test verisi: secrets prefix + cleanup; mevcut hesaplara dokunulmaz.
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
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2tr_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
TEACHER2_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
STUDENT2_EMAIL = f"{PFX}_s2@test.invalid"
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
    """Test verisi: 2 öğretmen + 2 öğrenci + 1 kitap (4 section).

    Görevler:
      - task_a    → bugün, planned=10, completed=0 (öğrenci complete + D/Y)
      - task_b    → bugün, planned=8, completed=0 (set-item-completed + D/Y)
      - task_c    → bugün, planned=5, completed=0 (öğrenci complete idempotent +
                     uncomplete D/Y temizleme)
      - task_d    → bugün, planned=10, completed=0 (koç result düzenleme)
      - other_task → diğer öğretmenin öğrencisi (sahiplik testi)
    """
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Result Test Öğretmen", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        teacher2 = User(
            email=TEACHER2_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Result Test Koç 2", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Result Test Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        student2 = User(
            email=STUDENT2_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Koç Öğrencisi", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        db.add_all([teacher, teacher2, student, student2])
        db.flush()
        student.teacher_id = teacher.id
        student2.teacher_id = teacher2.id

        subj = Subject(
            name=f"V2Result Ders {PFX}", order=999, is_builtin=False,
            teacher_id=teacher.id,
        )
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()

        book = Book(
            name=f"V2Result Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()

        sec_a = BookSection(book_id=book.id, label="A", test_count=20, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="B", test_count=20, order=1, topic_id=topic.id)
        sec_c = BookSection(book_id=book.id, label="C", test_count=20, order=2, topic_id=topic.id)
        sec_d = BookSection(book_id=book.id, label="D", test_count=20, order=3, topic_id=topic.id)
        db.add_all([sec_a, sec_b, sec_c, sec_d]); db.flush()

        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()

        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == sb.id))
        db.flush()

        # Her section'da yeterli rezerv: planned kadar
        sp_a = SectionProgress(student_book_id=sb.id, book_section_id=sec_a.id,
                               completed_count=0, reserved_count=10)
        sp_b = SectionProgress(student_book_id=sb.id, book_section_id=sec_b.id,
                               completed_count=0, reserved_count=8)
        sp_c = SectionProgress(student_book_id=sb.id, book_section_id=sec_c.id,
                               completed_count=0, reserved_count=5)
        sp_d = SectionProgress(student_book_id=sb.id, book_section_id=sec_d.id,
                               completed_count=0, reserved_count=10)
        db.add_all([sp_a, sp_b, sp_c, sp_d]); db.flush()

        today = date.today()

        task_a = Task(student_id=student.id, date=today, type=TaskType.TEST,
                      title="A", status=TaskStatus.PENDING, order=0)
        db.add(task_a); db.flush()
        item_a = TaskBookItem(task_id=task_a.id, book_id=book.id,
                              book_section_id=sec_a.id, planned_count=10, completed_count=0)
        db.add(item_a); db.flush()

        task_b = Task(student_id=student.id, date=today, type=TaskType.TEST,
                      title="B", status=TaskStatus.PENDING, order=1)
        db.add(task_b); db.flush()
        item_b = TaskBookItem(task_id=task_b.id, book_id=book.id,
                              book_section_id=sec_b.id, planned_count=8, completed_count=0)
        db.add(item_b); db.flush()

        task_c = Task(student_id=student.id, date=today, type=TaskType.TEST,
                      title="C", status=TaskStatus.PENDING, order=2)
        db.add(task_c); db.flush()
        item_c = TaskBookItem(task_id=task_c.id, book_id=book.id,
                              book_section_id=sec_c.id, planned_count=5, completed_count=0)
        db.add(item_c); db.flush()

        task_d = Task(student_id=student.id, date=today, type=TaskType.TEST,
                      title="D", status=TaskStatus.PENDING, order=3)
        db.add(task_d); db.flush()
        item_d = TaskBookItem(task_id=task_d.id, book_id=book.id,
                              book_section_id=sec_d.id, planned_count=10, completed_count=0)
        db.add(item_d); db.flush()

        # other_task → teacher2'nin öğrencisi (sahiplik testi)
        other_task = Task(student_id=student2.id, date=today, type=TaskType.TEST,
                          title="Other", status=TaskStatus.PENDING, order=0)
        db.add(other_task); db.flush()
        # Other'da item olsa da sahiplik 404'ten dönülmeli (item hiç sorgulanmadan)

        db.commit()
        return {
            "teacher_id": teacher.id,
            "teacher2_id": teacher2.id,
            "student_id": student.id,
            "student2_id": student2.id,
            "subject_id": subj.id,
            "topic_id": topic.id,
            "book_id": book.id,
            "sb_id": sb.id,
            "sec_ids": [sec_a.id, sec_b.id, sec_c.id, sec_d.id],
            "task_a_id": task_a.id, "item_a_id": item_a.id,
            "task_b_id": task_b.id, "item_b_id": item_b.id,
            "task_c_id": task_c.id, "item_c_id": item_c.id,
            "task_d_id": task_d.id, "item_d_id": item_d.id,
            "other_task_id": other_task.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        task_ids = [seed["task_a_id"], seed["task_b_id"], seed["task_c_id"],
                    seed["task_d_id"], seed["other_task_id"]]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
        db.execute(sa_delete(Task).where(Task.id.in_(task_ids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == seed["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == seed["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.id.in_(seed["sec_ids"])))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["student2_id"],
            seed["teacher_id"], seed["teacher2_id"],
        ])))
        # SuspiciousIp temizliği — testclient IP brute-force koruması
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def _item_correct_wrong(items: list[dict], item_id: int) -> tuple[int | None, int | None]:
    """Bir kalemin döner D/Y değerini bul."""
    for it in items:
        if it.get("id") == item_id:
            return it.get("correct"), it.get("wrong")
    return None, None


def main() -> int:
    print(f"\n=== API v2 görev sonucu (D/Y) smoke — prefix: {PFX} ===\n")
    seed = _seed()
    print(f"  seeded student={seed['student_id']} task_a={seed['task_a_id']}\n")

    try:
        client = TestClient(app)

        # ============ ÖĞRENCİ AKIŞI ============
        _login(client, STUDENT_EMAIL)

        # 1. complete + D/Y boş → tamamla, D/Y null
        r = client.post(f"/api/v2/student/tasks/{seed['task_a_id']}/complete", json={})
        body = r.json() if r.text else {}
        items = body.get("data", {}).get("items", [])
        c, w = _item_correct_wrong(items, seed["item_a_id"])
        ok = (r.status_code == 200
              and body.get("data", {}).get("status") == "completed"
              and c is None and w is None)
        check("1. öğrenci complete + D/Y boş → tamamla, D/Y null",
              ok, f"status={r.status_code} c={c} w={w}")

        # Görevi uncomplete et ki tekrar test edilebilsin
        client.post(f"/api/v2/student/tasks/{seed['task_a_id']}/uncomplete")

        # 2. complete + D/Y dolu → set
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_a_id']}/complete",
            json={"correct": 8, "wrong": 2},
        )
        body = r.json() if r.text else {}
        items = body.get("data", {}).get("items", [])
        c, w = _item_correct_wrong(items, seed["item_a_id"])
        ok = (r.status_code == 200 and c == 8 and w == 2)
        check("2. öğrenci complete + D/Y dolu (8+2=10) → set",
              ok, f"status={r.status_code} c={c} w={w}")

        # 3. KİTAPLI complete + D/Y c+w > completed → 200 (kitaplı görevde
        #    completed = test sayısı; D/Y = soru sayısı, bağımsız metric → kural yok)
        client.post(f"/api/v2/student/tasks/{seed['task_a_id']}/uncomplete")
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_a_id']}/complete",
            json={"correct": 95, "wrong": 5},   # 100 soru >> 10 test → KABUL
        )
        body = r.json() if r.text else {}
        items = body.get("data", {}).get("items", [])
        c, w = _item_correct_wrong(items, seed["item_a_id"])
        ok = (r.status_code == 200 and c == 95 and w == 5)
        check("3. KİTAPLI complete + D/Y (95D+5Y test-bağımsız) → 200",
              ok, f"status={r.status_code} c={c} w={w}")

        # 4. set-completed + D/Y boş → completed set, D/Y null
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_b_id']}/items/{seed['item_b_id']}/set-completed",
            json={"completed": 4},
        )
        body = r.json() if r.text else {}
        items = body.get("data", {}).get("items", [])
        c, w = _item_correct_wrong(items, seed["item_b_id"])
        completed = next((it.get("completed") for it in items if it.get("id") == seed["item_b_id"]), None)
        ok = (r.status_code == 200 and completed == 4 and c is None and w is None)
        check("4. set-completed + D/Y boş → completed=4, D/Y null",
              ok, f"status={r.status_code} completed={completed} c={c} w={w}")

        # 5. set-completed + D/Y dolu → set
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_b_id']}/items/{seed['item_b_id']}/set-completed",
            json={"completed": 8, "correct": 6, "wrong": 1},
        )
        body = r.json() if r.text else {}
        items = body.get("data", {}).get("items", [])
        c, w = _item_correct_wrong(items, seed["item_b_id"])
        ok = (r.status_code == 200 and c == 6 and w == 1)
        check("5. set-completed + D/Y dolu (6D + 1Y) → set",
              ok, f"status={r.status_code} c={c} w={w}")

        # 6. set-completed completed=0 → D/Y otomatik null (önceden 5'te 6/1 set edilmişti)
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_b_id']}/items/{seed['item_b_id']}/set-completed",
            json={"completed": 0},   # D/Y geçilmez; completed=0 olduğu için servis null'a düşürür
        )
        body = r.json() if r.text else {}
        items = body.get("data", {}).get("items", [])
        c, w = _item_correct_wrong(items, seed["item_b_id"])
        completed = next(
            (it.get("completed") for it in items if it.get("id") == seed["item_b_id"]),
            None,
        )
        ok = (r.status_code == 200 and completed == 0 and c is None and w is None)
        check("6. set-completed completed=0 → D/Y otomatik null'a düşer",
              ok, f"status={r.status_code} completed={completed} c={c} w={w}")

        # 7. set-completed D/Y negatif → 422
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_b_id']}/items/{seed['item_b_id']}/set-completed",
            json={"completed": 5, "correct": -1, "wrong": 2},
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 422
              and body.get("detail", {}).get("code") == "invalid_result_distribution")
        check("7. set-completed D/Y negatif → 422",
              ok, f"status={r.status_code} body={r.text[:160]}")

        # 8. uncomplete → D/Y null'a düşer
        # Önce complete et + D/Y set
        client.post(
            f"/api/v2/student/tasks/{seed['task_c_id']}/complete",
            json={"correct": 4, "wrong": 1},
        )
        # Şimdi uncomplete
        r = client.post(f"/api/v2/student/tasks/{seed['task_c_id']}/uncomplete")
        body = r.json() if r.text else {}
        items = body.get("data", {}).get("items", [])
        c, w = _item_correct_wrong(items, seed["item_c_id"])
        ok = (r.status_code == 200 and c is None and w is None)
        check("8. uncomplete → D/Y null'a düşer",
              ok, f"status={r.status_code} c={c} w={w}")

        # ============ KOÇ AKIŞI ============
        _login(client, TEACHER_EMAIL)

        # 9. koç POST result + D/Y → set
        r = client.post(
            f"/api/v2/teacher/tasks/{seed['task_d_id']}/items/{seed['item_d_id']}/result",
            json={"completed": 10, "correct": 7, "wrong": 3},
        )
        body = r.json() if r.text else {}
        # Teacher response'unda items farklı isimle dönebilir; backend item.correct_count alanına yazdı.
        # Doğrudan DB'den okuyarak doğrula (response yapısı kontrol etmiyoruz):
        ok = r.status_code == 200
        if ok:
            with SessionLocal() as db:
                it = db.get(TaskBookItem, seed["item_d_id"])
                ok = (it is not None and it.correct_count == 7 and it.wrong_count == 3
                      and it.completed_count == 10)
        check("9. koç result + D/Y (7D+3Y) → DB'de set + completed=10",
              ok, f"status={r.status_code} body={r.text[:200]}")

        # 10. koç result negatif D/Y → 422 (kitaplı görevde c+w>completed kuralı YOK;
        #     yalnız negatif değer reddedilir)
        r = client.post(
            f"/api/v2/teacher/tasks/{seed['task_d_id']}/items/{seed['item_d_id']}/result",
            json={"completed": 10, "correct": -5, "wrong": 3},
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 422
              and body.get("detail", {}).get("code") == "invalid_result_distribution")
        check("10. koç result negatif D → 422",
              ok, f"status={r.status_code} body={r.text[:160]}")

        # 11. koç result başkasının görevi → 404 task_not_found
        r = client.post(
            f"/api/v2/teacher/tasks/{seed['other_task_id']}/items/{seed['item_d_id']}/result",
            json={"completed": 5, "correct": 3, "wrong": 1},
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 404
              and body.get("detail", {}).get("code") in ("task_not_found", "not_found"))
        check("11. koç result başkasının görevi → 404",
              ok, f"status={r.status_code} body={r.text[:160]}")

        # 12. koç result olmayan item_id → 404 item_not_found
        r = client.post(
            f"/api/v2/teacher/tasks/{seed['task_d_id']}/items/99999999/result",
            json={"completed": 5, "correct": 3, "wrong": 1},
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 404
              and body.get("detail", {}).get("code") == "item_not_found")
        check("12. koç result olmayan item → 404 item_not_found",
              ok, f"status={r.status_code} body={r.text[:160]}")

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
