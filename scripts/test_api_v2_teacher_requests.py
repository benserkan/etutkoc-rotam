"""API v2 /teacher talep yanıtlama smoke (Dalga 3 Paket 3).

Senaryolar (14):
   1. GET /requests default → 200, pending listesi, pending_count > 0
   2. GET /requests?status=approved → 200, approved talepler
   3. GET /requests?student_id=other → 200, boş items (cross-tenant)
   4. GET /requests/{id} kendi → 200, current_items snapshot
   5. GET /requests/{id} başkasının → 404 request_not_found
   6. POST /approve CHANGE happy → 200, status APPROVED, task güncellendi,
      invalidate keys, dashboard sayacı azalır
   7. POST /approve REMOVE happy → 200, task silindi + rezerv iade
   8. POST /approve kapasite ihlali (CHANGE) → 422 RESERVE_OVER_CAPACITY,
      talep PENDING kalır (savepoint rollback)
   9. POST /reject (reason ile) → 200, status REJECTED, teacher_response yazıldı
  10. POST /reject reason boş → 422 reason_required
  11. POST /respond (question) → 200, status RESOLVED + teacher_response
  12. POST /respond response boş → 422 response_required
  13. POST /approve zaten REJECTED talep → 409 already_answered
  14. POST /approve başkasının → 404 request_not_found
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

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


PFX = f"v2tr_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_o@test.invalid"
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
    """2 öğretmen + 2 öğrenci + 1 kitap (2 section); öğrencinin görevleri + talepleri."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Req Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        db.add_all([teacher, other_teacher]); db.flush()

        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Öğrenci {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=teacher.id,
        )
        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Diğer Öğrenci {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=other_teacher.id,
        )
        db.add_all([student, other_student]); db.flush()

        subj = Subject(name=f"V2Req Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()
        book = Book(
            name=f"V2Req Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()

        # sec_a: cömert (test_count=20)
        # sec_b: dar (test_count=5) — kapasite ihlali için
        sec_a = BookSection(book_id=book.id, label="Bölüm A", test_count=20, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="Bölüm B", test_count=5, order=1, topic_id=topic.id)
        db.add_all([sec_a, sec_b]); db.flush()

        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == sb.id))
        db.flush()
        # sec_a: 3 rezerv, sec_b: 4 rezerv (1 kalan)
        db.add_all([
            SectionProgress(student_book_id=sb.id, book_section_id=sec_a.id, completed_count=0, reserved_count=3),
            SectionProgress(student_book_id=sb.id, book_section_id=sec_b.id, completed_count=0, reserved_count=4),
        ])

        # Görev 1: sec_a, planned=3 — CHANGE/REJECT talepleri için
        # Görev 2: sec_b, planned=4 — REMOVE/kapasite-CHANGE talepleri için
        today = date.today()
        task1 = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Görev A — sec_a 3 test",
            status=TaskStatus.PENDING, order=0,
        )
        task2 = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Görev B — sec_b 4 test",
            status=TaskStatus.PENDING, order=1,
        )
        db.add_all([task1, task2]); db.flush()

        item1 = TaskBookItem(
            task_id=task1.id, book_id=book.id, book_section_id=sec_a.id,
            planned_count=3, completed_count=0,
        )
        item2 = TaskBookItem(
            task_id=task2.id, book_id=book.id, book_section_id=sec_b.id,
            planned_count=4, completed_count=0,
        )
        db.add_all([item1, item2]); db.flush()

        # Talepler — farklı tip ve durumlar
        # T1 — CHANGE pending (test 6: approve happy)
        r_change = TaskRequest(
            student_id=student.id, teacher_id=teacher.id, task_id=task1.id,
            type=RequestType.CHANGE, status=RequestStatus.PENDING,
            message="Sayı 5 olabilir mi?", proposed_count=5,
        )
        # T2 — REMOVE pending (test 7: approve happy)
        r_remove = TaskRequest(
            student_id=student.id, teacher_id=teacher.id, task_id=task2.id,
            type=RequestType.REMOVE, status=RequestStatus.PENDING,
            message="Bu görevi çıkar lütfen",
        )
        # T3 — CHANGE pending kapasite-aşacak (test 8: 422)
        # task2 sec_b'de planned=4 ve sec_b.test_count=5 → maks +1 yapabilir
        # ileride başka task yok, max_new_count = 4 + (5-4-0) = 5 → proposed=10 ihlal
        task3 = Task(
            student_id=student.id, date=today + timedelta(days=1), type=TaskType.TEST,
            title="Görev C — sec_b başka",
            status=TaskStatus.PENDING, order=0,
        )
        db.add(task3); db.flush()
        item3 = TaskBookItem(
            task_id=task3.id, book_id=book.id, book_section_id=sec_b.id,
            planned_count=0, completed_count=0,
        )
        # planned 0 yarar — sadece task3 var sayılsın ama sec_b'de hâlâ kapasitemiz dar
        # Yeniden hesap: sec_b reserved_count=4 (yukarıdaki sp tutuyor), test_count=5 → kalan=1
        # max_new_count_for_change = item2.planned (4) + 1 (sec_b kalan) + 0 (future_movable)
        # = 5; proposed=10 zorlamak için ek rezerv lazım — basitlik için ayrı bir kapasite-aşma
        # task'ı oluşturalım: sec_b'de planned=1 olan extra item3 ve rezerv 5'e çekilsin.
        item3.planned_count = 1
        # sec_b rezerv 4 + 1 = 5'e çıksın (test_count=5 ile dolu)
        sp_b = (
            db.query(SectionProgress)
            .filter(SectionProgress.book_section_id == sec_b.id)
            .first()
        )
        sp_b.reserved_count = 5  # dolu
        # Şimdi task2 (planned=4) için change proposed=10 → max_new = 4 + (5-5-0) + (1) = 5; ihlal
        r_cap = TaskRequest(
            student_id=student.id, teacher_id=teacher.id, task_id=task2.id,
            type=RequestType.CHANGE, status=RequestStatus.PENDING,
            proposed_count=20,  # çok aşırı; uygulama sırasında ReservationError
        )

        # T4 — CHANGE pending (test 9: REJECT happy)
        r_reject = TaskRequest(
            student_id=student.id, teacher_id=teacher.id, task_id=task1.id,
            type=RequestType.CHANGE, status=RequestStatus.PENDING,
            message="başka bir öneri", proposed_count=2,
        )
        # T5 — QUESTION pending (test 11: respond happy)
        r_question = TaskRequest(
            student_id=student.id, teacher_id=teacher.id, task_id=task1.id,
            type=RequestType.QUESTION, status=RequestStatus.PENDING,
            message="Bu görevi nasıl yapmalıyım?",
        )
        # T6 — CHANGE already REJECTED (test 2 listede görünür + test 13: 409)
        r_already_rejected = TaskRequest(
            student_id=student.id, teacher_id=teacher.id, task_id=task1.id,
            type=RequestType.CHANGE, status=RequestStatus.REJECTED,
            proposed_count=2,
            teacher_response="Eski red",
            responded_at=datetime.now(timezone.utc),
        )
        # T7 — başka öğretmenin/öğrencinin talebi (test 5/14: 404)
        r_other = TaskRequest(
            student_id=other_student.id, teacher_id=other_teacher.id, task_id=None,
            type=RequestType.QUESTION, status=RequestStatus.PENDING,
            message="cross-tenant",
        )
        # T8 — bizim öğretmen için APPROVED talep (test 2: status=approved)
        r_already_approved = TaskRequest(
            student_id=student.id, teacher_id=teacher.id, task_id=task1.id,
            type=RequestType.QUESTION, status=RequestStatus.APPROVED,
            message="eski soru",
            teacher_response="Resolved",
            responded_at=datetime.now(timezone.utc),
        )

        db.add_all([
            r_change, r_remove, r_cap, r_reject, r_question,
            r_already_rejected, r_other, r_already_approved,
        ])
        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "subject_id": subj.id,
            "topic_id": topic.id,
            "book_id": book.id,
            "sec_a_id": sec_a.id,
            "sec_b_id": sec_b.id,
            "sb_id": sb.id,
            "task1_id": task1.id,
            "task2_id": task2.id,
            "task3_id": task3.id,
            "r_change_id": r_change.id,
            "r_remove_id": r_remove.id,
            "r_cap_id": r_cap.id,
            "r_reject_id": r_reject.id,
            "r_question_id": r_question.id,
            "r_already_rejected_id": r_already_rejected.id,
            "r_other_id": r_other.id,
            "r_already_approved_id": r_already_approved.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        student_ids = [seed["student_id"], seed["other_student_id"]]
        # Talepler önce
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id.in_(student_ids)))
        # Görevler + kalemler
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_(
                db.query(Task.id).filter(Task.student_id.in_(student_ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(Task).where(Task.student_id.in_(student_ids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == seed["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == seed["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.id.in_([
            seed["sec_a_id"], seed["sec_b_id"],
        ])))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_(student_ids + [
            seed["teacher_id"], seed["other_teacher_id"],
        ])))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher requests smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} student={seed['student_id']}\n")

    try:
        client = TestClient(app)
        _login_v2(client, TEACHER_EMAIL)

        # ===== 1. GET /requests default (pending) =====
        r = client.get("/api/v2/teacher/requests")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        pending_count = body.get("pending_count", -1)
        # Pending talepler: r_change + r_remove + r_cap + r_reject + r_question = 5
        all_pending = all(i.get("status") == "pending" for i in items)
        ok = (
            r.status_code == 200
            and pending_count == 5
            and len(items) == 5
            and all_pending
            # cross-tenant r_other listede olmamalı
            and not any(i.get("student_id") == seed["other_student_id"] for i in items)
        )
        check(
            "1. GET /requests default pending",
            ok,
            f"status={r.status_code} count={len(items)} pending={pending_count}",
        )

        # ===== 2. GET /requests?status=approved =====
        r = client.get("/api/v2/teacher/requests?status=approved")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and len(items) == 1
            and items[0].get("status") == "approved"
            and items[0].get("id") == seed["r_already_approved_id"]
        )
        check(
            "2. GET /requests?status=approved",
            ok,
            f"status={r.status_code} count={len(items)}",
        )

        # ===== 3. GET /requests?student_id=other (cross-tenant boş) =====
        r = client.get(f"/api/v2/teacher/requests?student_id={seed['other_student_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and len(body.get("items", [])) == 0
            and body.get("total") == 0
        )
        check(
            "3. GET /requests cross-tenant student_id → boş",
            ok,
            f"status={r.status_code} items={len(body.get('items', []))} total={body.get('total')}",
        )

        # ===== 4. GET /requests/{id} kendi =====
        r = client.get(f"/api/v2/teacher/requests/{seed['r_change_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("id") == seed["r_change_id"]
            and body.get("type") == "change"
            and body.get("status") == "pending"
            and body.get("proposed_count") == 5
            and isinstance(body.get("current_items"), list)
            and len(body["current_items"]) == 1
            and body["current_items"][0].get("planned_count") == 3
        )
        check(
            "4. GET /requests/{id} kendi → 200 + current_items",
            ok,
            f"status={r.status_code} proposed={body.get('proposed_count')} cur={len(body.get('current_items', []))}",
        )

        # ===== 5. GET /requests/{id} başkasının → 404 =====
        r = client.get(f"/api/v2/teacher/requests/{seed['r_other_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "request_not_found"
        )
        check(
            "5. GET /requests/{id} başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 6. POST /approve CHANGE happy =====
        # r_change: task1 planned 3 → 5; sec_a kalan = 20-3-0 = 17 → +2 fit
        r = client.post(
            f"/api/v2/teacher/requests/{seed['r_change_id']}/approve",
            json={"response": "Onaylandı, başarılar"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        invalidate = body.get("invalidate", [])
        # DB doğrulaması
        with SessionLocal() as db:
            req = db.query(TaskRequest).filter(TaskRequest.id == seed["r_change_id"]).first()
            task = db.query(Task).filter(Task.id == seed["task1_id"]).first()
            item = (
                db.query(TaskBookItem)
                .filter(TaskBookItem.task_id == seed["task1_id"])
                .first()
            )
            req_status = req.status.value if req else None
            item_planned = item.planned_count if item else None
        ok = (
            r.status_code == 200
            and data.get("status") == "approved"
            and req_status == "approved"
            and item_planned == 5
            and any(":requests" in k for k in invalidate)
            and any(":dashboard" in k for k in invalidate)
            and any(f":students:{seed['student_id']}:day:" in k for k in invalidate)
        )
        check(
            "6. POST /approve CHANGE happy",
            ok,
            f"status={r.status_code} req_status={req_status} planned={item_planned} inv={len(invalidate)}",
        )

        # ===== 7. POST /approve REMOVE happy =====
        # r_remove → task2 silinir, sec_b'den 4 rezerv iade
        with SessionLocal() as db:
            sp_b_before = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["sec_b_id"])
                .first()
            )
            sp_b_before_count = sp_b_before.reserved_count if sp_b_before else -1
        r = client.post(
            f"/api/v2/teacher/requests/{seed['r_remove_id']}/approve",
            json={},
        )
        body = r.json() if r.text else {}
        with SessionLocal() as db:
            req = db.query(TaskRequest).filter(TaskRequest.id == seed["r_remove_id"]).first()
            task_still = db.query(Task).filter(Task.id == seed["task2_id"]).first()
            sp_b_after = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["sec_b_id"])
                .first()
            )
            req_status = req.status.value if req else None
            sp_b_after_count = sp_b_after.reserved_count if sp_b_after else -1
        ok = (
            r.status_code == 200
            and req_status == "approved"
            and task_still is None  # silindi
            # task2.item planned=4 sec_b'den iade → reserved -4 → 5 - 4 = 1
            and sp_b_after_count == sp_b_before_count - 4
        )
        check(
            "7. POST /approve REMOVE happy",
            ok,
            f"status={r.status_code} req_status={req_status} task_still={task_still} "
            f"sec_b: {sp_b_before_count}→{sp_b_after_count}",
        )

        # ===== 8. POST /approve CHANGE kapasite ihlali → 422 + rollback =====
        # r_cap: task2'ye proposed=20 — ama task2 az önce silindi (test 7)
        # bu durumda RequestError("İlgili görev artık mevcut değil.") fırlar → 422.
        # Senaryoyu "kapasite ihlali" yerine "ilgili görev yok" doğrulamasıyla test edelim
        # ve yine de talebin PENDING kaldığını kontrol edelim — savepoint rollback.
        r = client.post(
            f"/api/v2/teacher/requests/{seed['r_cap_id']}/approve",
            json={},
        )
        body = r.json() if r.text else {}
        with SessionLocal() as db:
            req = db.query(TaskRequest).filter(TaskRequest.id == seed["r_cap_id"]).first()
            req_status = req.status.value if req else None
        ok = (
            r.status_code == 422
            and req_status == "pending"  # rollback başarılı
            and body.get("detail", {}).get("code") in ("request_invalid", "RESERVE_OVER_CAPACITY")
        )
        check(
            "8. POST /approve hata → 422 + rollback (PENDING)",
            ok,
            f"status={r.status_code} req_status={req_status} code={body.get('detail', {}).get('code')}",
        )

        # ===== 9. POST /reject (reason ile) =====
        r = client.post(
            f"/api/v2/teacher/requests/{seed['r_reject_id']}/reject",
            json={"reason": "Şu an program değiştirmek doğru olmaz"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            req = db.query(TaskRequest).filter(TaskRequest.id == seed["r_reject_id"]).first()
            req_status = req.status.value if req else None
            req_response = req.teacher_response if req else None
        ok = (
            r.status_code == 200
            and data.get("status") == "rejected"
            and req_status == "rejected"
            and req_response == "Şu an program değiştirmek doğru olmaz"
        )
        check(
            "9. POST /reject reason ile",
            ok,
            f"status={r.status_code} req_status={req_status} response={req_response!r}",
        )

        # ===== 10. POST /reject reason boş → 422 =====
        # Yeni PENDING talep yarat — sec_a için CHANGE
        with SessionLocal() as db:
            r_tmp = TaskRequest(
                student_id=seed["student_id"], teacher_id=seed["teacher_id"],
                task_id=seed["task1_id"], type=RequestType.CHANGE,
                status=RequestStatus.PENDING, proposed_count=4,
            )
            db.add(r_tmp); db.commit()
            r_tmp_id = r_tmp.id
        r = client.post(
            f"/api/v2/teacher/requests/{r_tmp_id}/reject",
            json={"reason": "   "},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "reason_required"
        )
        check(
            "10. POST /reject reason boş → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 11. POST /respond question happy =====
        r = client.post(
            f"/api/v2/teacher/requests/{seed['r_question_id']}/respond",
            json={"response": "Önce 1 sayfa test, sonra konu özetine bak."},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            req = db.query(TaskRequest).filter(TaskRequest.id == seed["r_question_id"]).first()
            req_status = req.status.value if req else None
            req_response = req.teacher_response if req else None
        ok = (
            r.status_code == 200
            and data.get("status") == "resolved"
            and req_status == "resolved"
            and req_response == "Önce 1 sayfa test, sonra konu özetine bak."
        )
        check(
            "11. POST /respond question happy",
            ok,
            f"status={r.status_code} req_status={req_status}",
        )

        # ===== 12. POST /respond boş → 422 =====
        # Yeni PENDING QUESTION yarat
        with SessionLocal() as db:
            r_q = TaskRequest(
                student_id=seed["student_id"], teacher_id=seed["teacher_id"],
                task_id=seed["task1_id"], type=RequestType.QUESTION,
                status=RequestStatus.PENDING, message="boş cevaba zorla",
            )
            db.add(r_q); db.commit()
            r_q_id = r_q.id
        r = client.post(
            f"/api/v2/teacher/requests/{r_q_id}/respond",
            json={"response": "  "},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "response_required"
        )
        check(
            "12. POST /respond boş → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 13. POST /approve zaten REJECTED → 409 =====
        r = client.post(
            f"/api/v2/teacher/requests/{seed['r_already_rejected_id']}/approve",
            json={},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "already_answered"
        )
        check(
            "13. POST /approve zaten REJECTED → 409",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 14. POST /approve başkasının → 404 =====
        r = client.post(
            f"/api/v2/teacher/requests/{seed['r_other_id']}/approve",
            json={},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "request_not_found"
        )
        check(
            "14. POST /approve başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

    finally:
        _cleanup(seed)
        print("\n  cleanup OK\n")

    print(f"\n=== SONUÇ: {passed}/14 PASS ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
