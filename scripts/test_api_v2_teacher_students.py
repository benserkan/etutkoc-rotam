"""API v2 /teacher students CRUD smoke (Dalga 3 Paket 4).

Senaryolar (14):
   1. POST /students happy → 200 + temp_password + id
   2. POST /students duplicate email → 409 email_taken
   3. POST /students 11. sınıf track yok → 422 track_required
   4. PATCH /students/{id} full_name + grade_level → 200
   5. PATCH başkasının → 404 student_not_found
   6. POST /deactivate → is_active=False
   7. POST /reactivate → is_active=True
   8. DELETE /students/{id} task'lı → 409 has_history
   9. DELETE /students/{id} temiz → 200 + kayıt yok
  10. GET /students/{id}/books → atanmış kitap listesi
  11. POST /students/{id}/books happy → 200 (SectionProgress kuruldu)
  12. POST /students/{id}/books duplicate → 409 already_assigned
  13. DELETE /students/{id}/books/{book_id} reserve var → 409 has_reservations
  14. POST /students/{id}/parents → ParentInvitation oluştu (token + 7 gün TTL)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    ParentInvitation,
    ParentStudentLink,
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


PFX = f"v2ts_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_other@test.invalid"
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
    """2 öğretmen + 1 başka-öğretmenin öğrencisi + 1 kitap (2 section)."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Stud Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",  # 15 öğrenci limiti — testte yeterli
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        db.add_all([teacher, other_teacher]); db.flush()

        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Başka Öğretmen Öğrencisi", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=other_teacher.id,
        )
        db.add(other_student); db.flush()

        # Kitap
        subj = Subject(name=f"V2Stud Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Test Konu", order=0, subject_id=subj.id)
        db.add(topic); db.flush()
        book = Book(
            name=f"V2Stud Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()
        sec_a = BookSection(book_id=book.id, label="Bölüm A", test_count=10, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="Bölüm B", test_count=5, order=1, topic_id=topic.id)
        db.add_all([sec_a, sec_b]); db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "other_student_id": other_student.id,
            "subject_id": subj.id,
            "topic_id": topic.id,
            "book_id": book.id,
            "sec_a_id": sec_a.id,
            "sec_b_id": sec_b.id,
        }


def _cleanup(seed: dict, created_student_ids: list[int]) -> None:
    with SessionLocal() as db:
        all_students = list(created_student_ids) + [seed["other_student_id"]]
        # Veli kayıtları
        db.execute(sa_delete(ParentInvitation).where(
            ParentInvitation.student_id.in_(all_students)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.student_id.in_(all_students)
        ))
        # Görevler ve kalemleri
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_(
                db.query(Task.id).filter(Task.student_id.in_(all_students)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(Task).where(Task.student_id.in_(all_students)))
        # Kitap atamaları
        sb_ids = [r[0] for r in db.query(StudentBook.id).filter(
            StudentBook.student_id.in_(all_students)
        ).all()]
        if sb_ids:
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.student_book_id.in_(sb_ids)
            ))
            db.execute(sa_delete(StudentBook).where(
                StudentBook.id.in_(sb_ids)
            ))
        db.execute(sa_delete(BookSection).where(
            BookSection.id.in_([seed["sec_a_id"], seed["sec_b_id"]])
        ))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_(
            all_students + [seed["teacher_id"], seed["other_teacher_id"]]
        )))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher students smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} book={seed['book_id']}\n")

    created_student_ids: list[int] = []
    s1_email = f"{PFX}_s1@test.invalid"
    s2_email = f"{PFX}_s2@test.invalid"
    s3_email = f"{PFX}_s3@test.invalid"  # 11. sınıf track-required

    try:
        client = TestClient(app)
        _login_v2(client, TEACHER_EMAIL)

        # ===== 1. POST /students happy =====
        r = client.post(
            "/api/v2/teacher/students",
            json={
                "full_name": "Yeni Öğrenci",
                "email": s1_email,
                "grade_level": 8,
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        new_id = data.get("id")
        if new_id:
            created_student_ids.append(new_id)
        ok = (
            r.status_code == 200
            and isinstance(new_id, int) and new_id > 0
            and isinstance(data.get("temp_password"), str)
            and len(data.get("temp_password", "")) >= 8
            and data.get("email") == s1_email
            and data.get("is_active") is True
            and any("teacher:" in k and ":students" in k for k in body.get("invalidate", []))
        )
        check(
            "1. POST /students happy",
            ok,
            f"status={r.status_code} id={new_id} pw_len={len(data.get('temp_password', ''))}",
        )

        # ===== 2. POST /students duplicate email → 409 =====
        r = client.post(
            "/api/v2/teacher/students",
            json={"full_name": "Aynı", "email": s1_email, "grade_level": 8},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "email_taken"
        )
        check(
            "2. POST /students duplicate email → 409",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 3. POST /students 11. sınıf track yok → 422 track_required =====
        r = client.post(
            "/api/v2/teacher/students",
            json={"full_name": "11. Sınıf", "email": s3_email, "grade_level": 11},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "track_required"
        )
        check(
            "3. POST /students 11. sınıf track yok → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 4. PATCH /students/{id} full_name + grade_level =====
        r = client.patch(
            f"/api/v2/teacher/students/{new_id}",
            json={"full_name": "Güncellenmiş Ad", "grade_level": 9},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("full_name") == "Güncellenmiş Ad"
            and data.get("grade_level") == 9
        )
        check(
            "4. PATCH /students/{id} happy",
            ok,
            f"status={r.status_code} name={data.get('full_name')} grade={data.get('grade_level')}",
        )

        # ===== 5. PATCH başkasının → 404 =====
        r = client.patch(
            f"/api/v2/teacher/students/{seed['other_student_id']}",
            json={"full_name": "Hacker"},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "student_not_found"
        )
        check(
            "5. PATCH başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 6. POST /deactivate → is_active=False =====
        r = client.post(f"/api/v2/teacher/students/{new_id}/deactivate")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("is_active") is False
        )
        check(
            "6. POST /deactivate",
            ok,
            f"status={r.status_code} is_active={data.get('is_active')}",
        )

        # ===== 7. POST /reactivate → is_active=True =====
        r = client.post(f"/api/v2/teacher/students/{new_id}/reactivate")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("is_active") is True
        )
        check(
            "7. POST /reactivate",
            ok,
            f"status={r.status_code} is_active={data.get('is_active')}",
        )

        # ===== 8. DELETE /students/{id} task'lı → 409 has_history =====
        # Önce öğrenciye bir task yarat
        with SessionLocal() as db:
            t = Task(
                student_id=new_id, date=date.today(),
                title="Test görev", order=0,
            )
            db.add(t); db.commit()
            task_id_added = t.id
        r = client.delete(f"/api/v2/teacher/students/{new_id}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "has_history"
            and body.get("detail", {}).get("details", {}).get("task_count") == 1
        )
        check(
            "8. DELETE task'lı → 409 has_history",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )
        # Task'ı geri sil (sonraki testler için temizlik)
        with SessionLocal() as db:
            db.execute(sa_delete(Task).where(Task.id == task_id_added))
            db.commit()

        # ===== 9. DELETE /students/{id} temiz → 200 =====
        # Yeni temiz bir öğrenci yarat ve sil
        r = client.post(
            "/api/v2/teacher/students",
            json={"full_name": "Silinecek", "email": s2_email, "grade_level": 8},
        )
        body = r.json() if r.text else {}
        s2_id = body.get("data", {}).get("id")
        r = client.delete(f"/api/v2/teacher/students/{s2_id}")
        body = r.json() if r.text else {}
        with SessionLocal() as db:
            still = db.query(User).filter(User.id == s2_id).first()
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("deleted") is True
            and still is None
        )
        check(
            "9. DELETE temiz → 200",
            ok,
            f"status={r.status_code} still={still}",
        )

        # ===== 10. GET /students/{id}/books → boş (henüz atama yok) =====
        r = client.get(f"/api/v2/teacher/students/{new_id}/books")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("items") == []
            and body.get("total") == 0
        )
        check(
            "10. GET /students/{id}/books başlangıçta boş",
            ok,
            f"status={r.status_code} total={body.get('total')}",
        )

        # ===== 11. POST /students/{id}/books happy =====
        r = client.post(
            f"/api/v2/teacher/students/{new_id}/books",
            json={"book_id": seed["book_id"]},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("book_id") == seed["book_id"]
            and data.get("section_count") == 2
            and data.get("section_total_tests") == 15
            and data.get("section_reserved_total") == 0
        )
        # DB'de SectionProgress kaydı oluştu mu?
        with SessionLocal() as db:
            sp_count = (
                db.query(SectionProgress)
                .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
                .filter(StudentBook.student_id == new_id)
                .count()
            )
        ok = ok and sp_count == 2
        check(
            "11. POST /students/{id}/books happy",
            ok,
            f"status={r.status_code} sections={data.get('section_count')} sp_rows={sp_count}",
        )

        # ===== 12. POST /students/{id}/books duplicate → 409 =====
        r = client.post(
            f"/api/v2/teacher/students/{new_id}/books",
            json={"book_id": seed["book_id"]},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "already_assigned"
        )
        check(
            "12. POST /books duplicate → 409 already_assigned",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 13. DELETE /books active rezerv → 409 has_reservations =====
        # SectionProgress.reserved_count = 3 yap (mock rezerv)
        with SessionLocal() as db:
            sp = (
                db.query(SectionProgress)
                .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
                .filter(StudentBook.student_id == new_id)
                .first()
            )
            sp.reserved_count = 3
            db.commit()
        r = client.delete(f"/api/v2/teacher/students/{new_id}/books/{seed['book_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "has_reservations"
        )
        check(
            "13. DELETE /books rezerv var → 409 has_reservations",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 14. POST /students/{id}/parents → davet oluştu =====
        r = client.post(
            f"/api/v2/teacher/students/{new_id}/parents",
            json={"parent_email": f"{PFX}_veli@test.invalid", "relation": "anne", "is_primary": True},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            inv = (
                db.query(ParentInvitation)
                .filter(
                    ParentInvitation.student_id == new_id,
                    ParentInvitation.invited_email == f"{PFX}_veli@test.invalid",
                )
                .first()
            )
        ok = (
            r.status_code == 200
            and isinstance(data.get("invitation_id"), int)
            and inv is not None
            and inv.token is not None and len(inv.token) >= 40
            and inv.consumed_at is None
            and inv.is_primary is True
        )
        check(
            "14. POST /students/{id}/parents davet oluştu",
            ok,
            f"status={r.status_code} inv_id={data.get('invitation_id')} token_ok={bool(inv and inv.token)}",
        )

    finally:
        _cleanup(seed, created_student_ids)
        print("\n  cleanup OK\n")

    print(f"\n=== SONUÇ: {passed}/14 PASS ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
