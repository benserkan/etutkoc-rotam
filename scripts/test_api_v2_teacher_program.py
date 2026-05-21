"""API v2 /teacher program CRUD smoke (Dalga 3 Paket 2).

Senaryolar (14):
   1. GET /students/{id}/day kendi öğrencisi → 200
   2. GET /students/{id}/day başkasının → 404 student_not_found
   3. GET /students/{id}/week → 200, 7 gün + week_start_anchor + notes
   4. POST /tasks happy → 200 + rezerv açılır + invalidate keys
   5. POST /tasks kapasite aşımı → 422 RESERVE_OVER_CAPACITY (rollback)
   6. PATCH /tasks/{id} title + scheduled_hour → 200
   7. PATCH /tasks/{id}/items/{item_id} planned 3→5 → rezerv +2
   8. PATCH /tasks/{id}/items/{item_id} planned 5→1 ama completed=2 → 422 planned_below_completed
   9. DELETE /tasks/{id} → rezerv iadesi + 200
  10. DELETE /tasks başkasının → 404 task_not_found
  11. POST /tasks/{id}/items invalid section/book uyumsuz → 422 invalid_section
  12. POST /bulk-tasks atomik happy (3 görev) → 200
  13. POST /bulk-tasks bir kapasite ihlali → 422 + hiçbir görev kalmaz
  14. POST /tasks başkasının öğrencisi → 404 student_not_found
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
    Task,
    TaskBookItem,
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2tp_{secrets.token_hex(3)}"
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
    """Test verisi: 2 öğretmen + 2 öğrenci (sahip ayrı) + 1 kitap (3 section + atama)."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Prog Test Öğretmen", role=UserRole.TEACHER, is_active=True,
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

        subj = Subject(name=f"V2Prog Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()
        book = Book(
            name=f"V2Prog Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()

        # sec_a: cömert (test_count=20) — happy/PATCH için
        # sec_b: dar (test_count=3) — kapasite ihlali için
        # sec_c: hiç atanmamış (Book sahipliği testi)
        sec_a = BookSection(book_id=book.id, label="Bölüm A", test_count=20, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="Bölüm B", test_count=3, order=1, topic_id=topic.id)
        sec_c = BookSection(book_id=book.id, label="Bölüm C", test_count=10, order=2, topic_id=topic.id)
        db.add_all([sec_a, sec_b, sec_c]); db.flush()

        # Kitap öğrenciye ATA — testlerin önkoşulu
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == sb.id))
        db.flush()
        # Boş SP'ler — temiz başlangıç
        db.add_all([
            SectionProgress(student_book_id=sb.id, book_section_id=sec_a.id, completed_count=0, reserved_count=0),
            SectionProgress(student_book_id=sb.id, book_section_id=sec_b.id, completed_count=0, reserved_count=0),
            SectionProgress(student_book_id=sb.id, book_section_id=sec_c.id, completed_count=0, reserved_count=0),
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
            "sec_c_id": sec_c.id,
            "sb_id": sb.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        student_ids = [seed["student_id"], seed["other_student_id"]]
        # Tüm task'ları + book item'ları sil (testte oluşan dahil)
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_(
                db.query(Task.id).filter(Task.student_id.in_(student_ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(Task).where(Task.student_id.in_(student_ids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == seed["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == seed["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.id.in_([
            seed["sec_a_id"], seed["sec_b_id"], seed["sec_c_id"],
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
    print(f"\n=== API v2 /teacher program smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} student={seed['student_id']} book={seed['book_id']}\n")

    today_iso = date.today().isoformat()
    yarın = (date.today() + timedelta(days=1)).isoformat()

    try:
        client = TestClient(app)
        _login_v2(client, TEACHER_EMAIL)

        # ===== 1. /day kendi öğrencisi =====
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/day")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("student_id") == seed["student_id"]
            and "tasks" in body and isinstance(body["tasks"], list)
        )
        check(
            "1. /day kendi öğrencisi",
            ok,
            f"status={r.status_code} keys={list(body.keys())[:6]}",
        )

        # ===== 2. /day başkasının → 404 =====
        r = client.get(f"/api/v2/teacher/students/{seed['other_student_id']}/day")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "student_not_found"
        )
        check(
            "2. /day başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 3. /week happy =====
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/week")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and len(body.get("days", [])) == 7
            and "week_start_anchor" in body
            and isinstance(body.get("notes"), list)
        )
        check(
            "3. /week happy",
            ok,
            f"status={r.status_code} days={len(body.get('days', []))}",
        )

        # ===== 4. POST /tasks happy =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/tasks",
            json={
                "date": today_iso,
                "type": "test",
                "title": "Smoke happy görev",
                "scheduled_hour": 14,
                "items": [{
                    "book_id": seed["book_id"],
                    "section_id": seed["sec_a_id"],
                    "planned_count": 3,
                }],
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        invalidate = body.get("invalidate", [])
        happy_task_id = data.get("id")
        happy_item_id = (data.get("items") or [{}])[0].get("id")
        ok = (
            r.status_code == 200
            and data.get("title") == "Smoke happy görev"
            and data.get("planned_count") == 3
            and len(data.get("items", [])) == 1
            and data.get("items")[0]["section_reserved_count"] == 3
            and any(":day:" in k for k in invalidate)
            and any("teacher:" in k for k in invalidate)
        )
        check(
            "4. POST /tasks happy",
            ok,
            f"status={r.status_code} reserved={data.get('items', [{}])[0].get('section_reserved_count')} invalidate={len(invalidate)}",
        )

        # ===== 5. POST /tasks kapasite aşımı (sec_b test_count=3, planned=10) → 422 =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/tasks",
            json={
                "date": today_iso,
                "type": "test",
                "title": "Kapasite aşacak",
                "items": [{
                    "book_id": seed["book_id"],
                    "section_id": seed["sec_b_id"],
                    "planned_count": 10,
                }],
            },
        )
        body = r.json() if r.text else {}
        # Rollback doğrulaması: sec_b'de rezerv hâlâ 0 olmalı
        with SessionLocal() as db:
            sp = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["sec_b_id"])
                .first()
            )
            sec_b_reserved = sp.reserved_count if sp else -1
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "RESERVE_OVER_CAPACITY"
            and sec_b_reserved == 0  # rollback başarılı
        )
        check(
            "5. POST /tasks kapasite → 422 + rollback",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')} sec_b_reserved={sec_b_reserved}",
        )

        # ===== 6. PATCH /tasks/{id} title + scheduled_hour =====
        r = client.patch(
            f"/api/v2/teacher/tasks/{happy_task_id}",
            json={"title": "Güncellenmiş başlık", "scheduled_hour": 9},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("title") == "Güncellenmiş başlık"
            and data.get("scheduled_hour") == "09:00"
        )
        check(
            "6. PATCH /tasks happy",
            ok,
            f"status={r.status_code} title={data.get('title')} hour={data.get('scheduled_hour')}",
        )

        # ===== 7. PATCH /tasks/{id}/items/{item_id} planned 3→5 → rezerv +2 =====
        r = client.patch(
            f"/api/v2/teacher/tasks/{happy_task_id}/items/{happy_item_id}",
            json={"planned_count": 5},
        )
        body = r.json() if r.text else {}
        with SessionLocal() as db:
            sp = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["sec_a_id"])
                .first()
            )
            sec_a_reserved = sp.reserved_count if sp else -1
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("planned_count") == 5
            and sec_a_reserved == 5
        )
        check(
            "7. PATCH item 3→5 → rezerv 5",
            ok,
            f"status={r.status_code} planned={body.get('data', {}).get('planned_count')} sec_a_reserved={sec_a_reserved}",
        )

        # ===== 8. PATCH item planned ALTINDA completed → 422 =====
        # Önce completed=2 yap (test mock'unun bypass eden hızlı yolu olmadığı için
        # manuel olarak set ediyoruz — service kontratını test ediyoruz)
        with SessionLocal() as db:
            it = db.query(TaskBookItem).filter(TaskBookItem.id == happy_item_id).first()
            it.completed_count = 2
            db.commit()
        r = client.patch(
            f"/api/v2/teacher/tasks/{happy_task_id}/items/{happy_item_id}",
            json={"planned_count": 1},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "planned_below_completed"
        )
        check(
            "8. PATCH item planned<completed → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 9. DELETE /tasks/{id} → rezerv iadesi =====
        r = client.delete(f"/api/v2/teacher/tasks/{happy_task_id}")
        body = r.json() if r.text else {}
        with SessionLocal() as db:
            sp = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["sec_a_id"])
                .first()
            )
            sec_a_reserved_after = sp.reserved_count if sp else -1
            task_still = db.query(Task).filter(Task.id == happy_task_id).first()
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("deleted") is True
            # planned=5, completed=2 → released = 3, reserved 5 → 2 olmalı (completed kısma dokunulmaz)
            and sec_a_reserved_after == 2
            and task_still is None
        )
        check(
            "9. DELETE /tasks → rezerv iadesi",
            ok,
            f"status={r.status_code} sec_a_reserved={sec_a_reserved_after} task_deleted={task_still is None}",
        )

        # ===== 10. DELETE /tasks başkasının → 404 =====
        # Başkasının öğrencisi için bir task üret (admin-level via DB seed)
        with SessionLocal() as db:
            from app.models import TaskStatus, TaskType as TT
            other_task = Task(
                student_id=seed["other_student_id"], date=date.today(),
                type=TT.TEST, title="başkasınınki", status=TaskStatus.PENDING, order=0,
            )
            db.add(other_task); db.commit()
            other_task_id = other_task.id
        r = client.delete(f"/api/v2/teacher/tasks/{other_task_id}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "task_not_found"
        )
        check(
            "10. DELETE başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 11. POST /tasks/{id}/items invalid section → 422 =====
        # Yeni temiz happy task lazım (Test 9'da happy_task_id silindi). Önce kur.
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/tasks",
            json={
                "date": today_iso,
                "type": "test",
                "title": "İkinci görev",
                "items": [{
                    "book_id": seed["book_id"],
                    "section_id": seed["sec_c_id"],
                    "planned_count": 2,
                }],
            },
        )
        assert r.status_code == 200, f"setup failed: {r.text}"
        second_task_id = r.json()["data"]["id"]

        r = client.post(
            f"/api/v2/teacher/tasks/{second_task_id}/items",
            json={
                # sec_a_id ait olduğu book_id ile uyumsuz şekilde dummy 99999 ver
                "book_id": 99999,
                "section_id": seed["sec_a_id"],
                "planned_count": 1,
            },
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "invalid_section"
        )
        check(
            "11. POST item invalid section → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 12. POST /bulk-tasks atomik happy (3 görev, sec_a yetiyor) =====
        # sec_a: total=20, mevcut rezerv=2 (Test 9 sonrası completed kısmı), kalan ≥ 18
        # 3 görev × 3 test = 9 test → fazlasıyla yetiyor
        # NOT: second_task_id (sec_c) hâlâ duruyor; sec_c'ye dokunmuyoruz.
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/bulk-tasks",
            json={
                "tasks": [
                    {
                        "date": yarın, "type": "test", "title": f"Bulk #{i}",
                        "items": [{
                            "book_id": seed["book_id"],
                            "section_id": seed["sec_a_id"],
                            "planned_count": 3,
                        }],
                    }
                    for i in range(3)
                ]
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("created_count") == 3
            and len(data.get("task_ids", [])) == 3
        )
        check(
            "12. POST /bulk-tasks happy",
            ok,
            f"status={r.status_code} created={data.get('created_count')}",
        )

        # ===== 13. POST /bulk-tasks atomik kapasite ihlali → 422 + hiçbir görev kalmaz =====
        # Önce mevcut sec_b rezerv durumunu al
        with SessionLocal() as db:
            sp_before = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["sec_b_id"])
                .first()
            )
            sec_b_reserved_before = sp_before.reserved_count if sp_before else 0
            tasks_before = (
                db.query(Task)
                .filter(Task.student_id == seed["student_id"], Task.date == date.today() + timedelta(days=2))
                .count()
            )
        # 1. görev OK (sec_a planned=2), 2. görev kapasite aşacak (sec_b planned=10 ama test_count=3)
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/bulk-tasks",
            json={
                "tasks": [
                    {
                        "date": (date.today() + timedelta(days=2)).isoformat(),
                        "type": "test", "title": "Bulk-OK",
                        "items": [{
                            "book_id": seed["book_id"],
                            "section_id": seed["sec_a_id"],
                            "planned_count": 2,
                        }],
                    },
                    {
                        "date": (date.today() + timedelta(days=2)).isoformat(),
                        "type": "test", "title": "Bulk-FAIL",
                        "items": [{
                            "book_id": seed["book_id"],
                            "section_id": seed["sec_b_id"],
                            "planned_count": 10,
                        }],
                    },
                ]
            },
        )
        body = r.json() if r.text else {}
        with SessionLocal() as db:
            sp_after = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["sec_b_id"])
                .first()
            )
            sec_b_reserved_after = sp_after.reserved_count if sp_after else 0
            tasks_after = (
                db.query(Task)
                .filter(Task.student_id == seed["student_id"], Task.date == date.today() + timedelta(days=2))
                .count()
            )
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "RESERVE_OVER_CAPACITY"
            and sec_b_reserved_after == sec_b_reserved_before  # değişmemiş
            and tasks_after == tasks_before                    # hiç görev eklenmemiş
        )
        check(
            "13. POST /bulk-tasks atomik rollback",
            ok,
            f"status={r.status_code} sec_b={sec_b_reserved_before}→{sec_b_reserved_after} tasks={tasks_before}→{tasks_after}",
        )

        # ===== 14. POST /tasks başkasının öğrencisi → 404 =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['other_student_id']}/tasks",
            json={
                "date": today_iso, "type": "test", "title": "İzinsiz",
                "items": [{
                    "book_id": seed["book_id"],
                    "section_id": seed["sec_a_id"],
                    "planned_count": 1,
                }],
            },
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "student_not_found"
        )
        check(
            "14. POST /tasks başkasının → 404",
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
