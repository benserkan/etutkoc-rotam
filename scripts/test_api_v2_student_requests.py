"""API v2 /student requests smoke (Dalga 2 Paket 3).

Talep sistemi — change/replace/remove/question/add/withdraw + list.
Mevcut Jinja /student/tasks/{id}/request-* uçlarının JSON karşılığı.

Senaryolar (14):
   1. POST change happy path → 200 + status=pending + invalidate 4 anahtar
   2. POST change zaten PENDING var → 409 request_already_pending
   3. POST change tamamlanmış görev → 422 task_already_completed
   4. POST change başkasının görevi → 404 task_not_found
   5. POST replace happy path → 200 + status=pending
   6. POST remove happy path → 200 + status=pending
   7. POST question (tamamlanmış görev üzerinde) → 200 (her zaman serbest)
   8. POST question boş mesaj → 400 request_error
   9. POST add happy path (bugün/gelecek) → 200 + status=pending
  10. POST add geçmiş gün → 400 past_day_blocked
  11. POST withdraw kendi PENDING → 200 + status=withdrawn
  12. POST withdraw başkasının → 404 request_not_found
  13. POST withdraw zaten withdrawn → 400 request_error
  14. GET /requests?status=pending|all → filtreleme + pending_count

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

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    RequestStatus,
    RequestType,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskRequest,
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
    """Test verisi: 1 öğretmen + 2 öğrenci + 1 kitap (3 section).

    Görevler:
      - task_change   → bugün, planned=3 (change/replace/remove/question için)
      - task_done     → dün, COMPLETED (tamamlanmış üzerine talep testi)
      - task_other    → diğer öğrencinin görevi (sahiplik testi)
    """
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Req Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Req Test Öğrenci", role=UserRole.STUDENT, is_active=True,
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

        subj = Subject(name=f"V2Req Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()

        book = Book(
            name=f"V2Req Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()

        sec_a = BookSection(book_id=book.id, label="Bölüm A", test_count=10, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="Bölüm B", test_count=10, order=1, topic_id=topic.id)
        sec_c = BookSection(book_id=book.id, label="Bölüm C", test_count=10, order=2, topic_id=topic.id)
        db.add_all([sec_a, sec_b, sec_c]); db.flush()

        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()

        # Önceki run yetimleri sil (SQLite PK reuse koruması)
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == sb.id))
        db.flush()

        # SectionProgress'ler — change için sec_a, replace için sec_b'ye geçiş, done için sec_c
        sp_a = SectionProgress(student_book_id=sb.id, book_section_id=sec_a.id,
                               completed_count=0, reserved_count=3)
        sp_b = SectionProgress(student_book_id=sb.id, book_section_id=sec_b.id,
                               completed_count=0, reserved_count=0)
        sp_c = SectionProgress(student_book_id=sb.id, book_section_id=sec_c.id,
                               completed_count=2, reserved_count=0)
        db.add_all([sp_a, sp_b, sp_c]); db.flush()

        today = date.today()
        # task_change — bugün, planned=3 (sec_a.reserved=3 ile uyumlu)
        task_change = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Bugünkü görev", status=TaskStatus.PENDING, order=0,
        )
        db.add(task_change); db.flush()
        item_change = TaskBookItem(
            task_id=task_change.id, book_id=book.id, book_section_id=sec_a.id,
            planned_count=3, completed_count=0,
        )
        db.add(item_change); db.flush()

        # task_done — dün, COMPLETED (sec_c, planned=2, completed=2)
        task_done = Task(
            student_id=student.id, date=today - timedelta(days=1), type=TaskType.TEST,
            title="Tamamlanmış görev", status=TaskStatus.COMPLETED, order=0,
        )
        db.add(task_done); db.flush()
        item_done = TaskBookItem(
            task_id=task_done.id, book_id=book.id, book_section_id=sec_c.id,
            planned_count=2, completed_count=2,
        )
        db.add(item_done); db.flush()

        # task_other — diğer öğrenciye ait (sahiplik testi)
        task_other = Task(
            student_id=other_student.id, date=today, type=TaskType.TEST,
            title="Diğer öğrencinin görevi", status=TaskStatus.PENDING, order=0,
        )
        db.add(task_other); db.flush()

        # other_student için bir TaskRequest yarat (withdraw başkasınınki testi)
        other_req = TaskRequest(
            student_id=other_student.id, teacher_id=teacher.id,
            task_id=task_other.id, type=RequestType.QUESTION,
            status=RequestStatus.PENDING, message="diğer öğrencinin sorusu",
        )
        db.add(other_req); db.flush()

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
            "sec_a_id": sec_a.id,
            "sec_b_id": sec_b.id,
            "sec_c_id": sec_c.id,
            "task_change_id": task_change.id,
            "task_done_id": task_done.id,
            "task_other_id": task_other.id,
            "other_req_id": other_req.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        student_ids = [seed["student_id"], seed["other_student_id"]]
        # Tüm TaskRequest'leri sil (test sırasında yaratılanlar dahil)
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id.in_(student_ids)))
        task_ids = [
            seed["task_change_id"], seed["task_done_id"], seed["task_other_id"],
        ]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
        # Test sırasında "add" talebi onaylanmadığı için yeni Task yaratılmaz.
        # Yine de student_id'ye bağlı tüm task'ları temizle (defansif).
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_(
                db.query(Task.id).filter(Task.student_id.in_(student_ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(Task).where(Task.student_id.in_(student_ids)))
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


def _logout_v2(client: TestClient) -> None:
    client.post("/api/v2/auth/logout")


def _has_invalidate_keys(invalidate: list[str]) -> bool:
    """change/replace/remove/question için 4 anahtar (requests + badges + day + summary)."""
    return (
        any(":requests" in k for k in invalidate)
        and any("badges:" in k for k in invalidate)
        and any(":day:" in k for k in invalidate)
        and any(":summary:" in k for k in invalidate)
    )


def main() -> int:
    print(f"\n=== API v2 /student requests smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded student={seed['student_id']} task_change={seed['task_change_id']}\n")

    try:
        client = TestClient(app)
        _login_v2(client, STUDENT_EMAIL)

        # ===== 1. POST change happy path → 200 + status=pending =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_change_id']}/requests/change",
            json={"proposed_count": 5, "message": "5 yapmak istiyorum"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        invalidate = body.get("invalidate", [])
        change_req_id = data.get("id")
        ok = (
            r.status_code == 200
            and data.get("type") == "change"
            and data.get("status") == "pending"
            and data.get("proposed_count") == 5
            and _has_invalidate_keys(invalidate)
        )
        check(
            "1. change happy path",
            ok,
            f"status={r.status_code} type={data.get('type')} req_status={data.get('status')} invalidate={invalidate}",
        )

        # ===== 2. POST change ZATEN pending → 409 =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_change_id']}/requests/change",
            json={"proposed_count": 4},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "request_already_pending"
        )
        check(
            "2. change zaten pending → 409",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 3. POST change tamamlanmış görev → 422 task_already_completed =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_done_id']}/requests/change",
            json={"proposed_count": 4},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "task_already_completed"
        )
        check(
            "3. change tamamlanmış → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 4. POST change başkasının görevi → 404 task_not_found =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_other_id']}/requests/change",
            json={"proposed_count": 4},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "task_not_found"
        )
        check(
            "4. change başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # Önce mevcut PENDING change talebini withdraw ile temizle (Test 5-6 için yer açalım)
        r_wd = client.post(f"/api/v2/student/requests/{change_req_id}/withdraw")
        assert r_wd.status_code == 200, f"setup withdraw failed: {r_wd.text}"

        # ===== 5. POST replace happy path → 200 =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_change_id']}/requests/replace",
            json={
                "new_book_id": seed["book_id"],
                "new_section_id": seed["sec_b_id"],
                "new_count": 4,
                "message": "Bölüm B'ye geç",
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        replace_req_id = data.get("id")
        ok = (
            r.status_code == 200
            and data.get("type") == "replace"
            and data.get("status") == "pending"
            and data.get("proposed_section_id") == seed["sec_b_id"]
        )
        check(
            "5. replace happy path",
            ok,
            f"status={r.status_code} type={data.get('type')} sec={data.get('proposed_section_id')}",
        )

        # replace'i withdraw ederek tek-PENDING kuralını koru
        client.post(f"/api/v2/student/requests/{replace_req_id}/withdraw")

        # ===== 6. POST remove happy path → 200 =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_change_id']}/requests/remove",
            json={"message": "Bu görevi çıkar"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        remove_req_id = data.get("id")
        ok = (
            r.status_code == 200
            and data.get("type") == "remove"
            and data.get("status") == "pending"
        )
        check(
            "6. remove happy path",
            ok,
            f"status={r.status_code} type={data.get('type')}",
        )

        # ===== 7. POST question (tamamlanmış görev üzerinde) → 200 =====
        # Question her zaman serbest (tamamlanmış görev + paralel PENDING fark etmez).
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_done_id']}/requests/question",
            json={"message": "Bu görev hakkında bir sorum var"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("type") == "question"
            and data.get("status") == "pending"
            and data.get("task_id") == seed["task_done_id"]
        )
        check(
            "7. question tamamlanmış üzerinde → 200",
            ok,
            f"status={r.status_code} type={data.get('type')}",
        )

        # ===== 8. POST question boş mesaj → 400 request_error =====
        r = client.post(
            f"/api/v2/student/tasks/{seed['task_change_id']}/requests/question",
            json={"message": "   "},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 400
            and body.get("detail", {}).get("code") == "request_error"
        )
        check(
            "8. question boş mesaj → 400",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 9. POST add happy path (yarın) → 200 =====
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post(
            f"/api/v2/student/days/{tomorrow}/requests/add",
            json={
                "book_id": seed["book_id"],
                "section_id": seed["sec_b_id"],
                "proposed_count": 3,
                "message": "Yarın için ek görev",
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("type") == "add"
            and data.get("status") == "pending"
            and data.get("proposed_date") == tomorrow
        )
        check(
            "9. add yarın → 200",
            ok,
            f"status={r.status_code} type={data.get('type')} date={data.get('proposed_date')}",
        )

        # ===== 10. POST add geçmiş gün → 400 past_day_blocked =====
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        r = client.post(
            f"/api/v2/student/days/{yesterday}/requests/add",
            json={
                "book_id": seed["book_id"],
                "section_id": seed["sec_b_id"],
                "proposed_count": 1,
            },
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 400
            and body.get("detail", {}).get("code") == "past_day_blocked"
        )
        check(
            "10. add geçmiş gün → 400",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 11. POST withdraw kendi PENDING → 200 + withdrawn =====
        r = client.post(f"/api/v2/student/requests/{remove_req_id}/withdraw")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("status") == "withdrawn"
        )
        check(
            "11. withdraw kendi PENDING → 200",
            ok,
            f"status={r.status_code} req_status={data.get('status')}",
        )

        # ===== 12. POST withdraw başkasının → 404 =====
        r = client.post(f"/api/v2/student/requests/{seed['other_req_id']}/withdraw")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "request_not_found"
        )
        check(
            "12. withdraw başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 13. POST withdraw zaten withdrawn → 400 request_error =====
        r = client.post(f"/api/v2/student/requests/{remove_req_id}/withdraw")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 400
            and body.get("detail", {}).get("code") == "request_error"
        )
        check(
            "13. withdraw zaten withdrawn → 400",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 14. GET /requests?status=pending ve ?status=all → filtreleme =====
        # Şu an: 1 add(pending) + 1 question(pending) + 1 question(pending sec b boş)
        # withdraw'lı 3 tane (change, replace, remove) + boş-mesaj reddedildi
        r_pending = client.get("/api/v2/student/requests?status=pending")
        r_all = client.get("/api/v2/student/requests?status=all")
        body_p = r_pending.json() if r_pending.text else {}
        body_a = r_all.json() if r_all.text else {}
        items_p = body_p.get("items", [])
        items_a = body_a.get("items", [])
        pending_count_p = body_p.get("pending_count", -1)
        # Filtre doğruluğu: pending listede sadece pending statüleri olmalı
        only_pending = all(it.get("status") == "pending" for it in items_p)
        # all >= pending sayısı (en azından)
        len_ok = len(items_a) >= len(items_p)
        # pending_count alanı tutarlı olmalı
        count_ok = pending_count_p == sum(1 for it in items_a if it.get("status") == "pending")
        ok = (
            r_pending.status_code == 200
            and r_all.status_code == 200
            and only_pending
            and len_ok
            and count_ok
        )
        check(
            "14. /requests filtreleme + pending_count",
            ok,
            f"pending={len(items_p)} all={len(items_a)} pending_count={pending_count_p} only_pending={only_pending}",
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
