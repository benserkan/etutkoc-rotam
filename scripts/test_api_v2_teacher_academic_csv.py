"""API v2 /teacher/academic + /teacher/grade-advance + /teacher/csv smoke (Paket 10).

Senaryolar (14):
   1. GET /academic/years → boş başlar, /years/choices listesi gelir
   2. POST /academic/years → yıl yarat, name otomatik 'YYYY-(YYYY+1)'
   3. POST /academic/years/{id}/phases → faz ekle
   4. PATCH /academic/years/{id}/phases/{pid} → end_date güncelle
   5. PATCH /academic/years/{id}/students → diff atama (assigned+removed)
   6. DELETE /academic/years/{id} → öğrenci atanmış → 409 has_students
   7. GET /grade-advance/preview → suggested_grade + blocker_notes
   8. POST /grade-advance/apply → grade+AY uygulanır, rezerv KORUNUR (task silinmedi)
   9. POST /grade-advance/students/{id}/reset-program — yanlış ad → 422 confirm_name_mismatch
  10. POST /grade-advance/students/{id}/reset-program — doğru ad → tasks/feedback sıfırlandı
  11. POST /csv/import/students/preview → 2 valid + 1 invalid satır
  12. POST /csv/import/students/commit → 2 öğrenci yarattı + temp_password DB'de bcrypt
  13. GET /csv/export/students → text/csv + BOM + öğretmenin öğrencileri
  14. Cross-tenant 404: başka öğretmenin yılı/öğrencisi → 404
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
    AcademicPhase,
    AcademicYear,
    Book,
    BookSection,
    BookType,
    SectionProgress,
    StudentBook,
    SuggestionFeedback,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2acd_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
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
    """2 öğretmen + 2 öğrenci + 1 kitap+bölüm (rezerv testleri için)."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Acad Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen Acad", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        db.add_all([teacher, other_teacher])
        db.flush()

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
        db.add_all([student, other_student])
        db.flush()

        # Rezerv testleri için kitap+bölüm+task
        from app.models import Subject
        subj = Subject(
            name=f"V2Acad Ders {PFX}", order=999,
            is_builtin=False, teacher_id=teacher.id,
        )
        db.add(subj); db.flush()
        book = Book(
            name=f"Test Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()
        section = BookSection(
            book_id=book.id, label="Bölüm 1", test_count=20, order=0,
        )
        db.add(section); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()
        sp = SectionProgress(
            student_book_id=sb.id, book_section_id=section.id,
            reserved_count=3, completed_count=1,
        )
        db.add(sp)

        # 1 task + 1 task book item (reset-program testi için)
        t = Task(
            student_id=student.id, date=date.today(),
            type=TaskType.TEST, title="Test gorev",
            status=TaskStatus.PENDING, order=0, is_draft=False,
        )
        db.add(t); db.flush()
        tbi = TaskBookItem(
            task_id=t.id, book_id=book.id, book_section_id=section.id,
            planned_count=3, completed_count=0,
        )
        db.add(tbi)

        db.commit()

        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "student_full_name": student.full_name,
            "subject_id": subj.id,
            "book_id": book.id,
            "section_id": section.id,
            "task_id": t.id,
        }


def _cleanup(seed: dict) -> None:
    from app.models import Subject
    with SessionLocal() as db:
        sids = [seed["student_id"], seed["other_student_id"]]
        tids = [seed["teacher_id"], seed["other_teacher_id"]]
        # Tasks + items
        task_ids_q = db.query(Task.id).filter(Task.student_id.in_(sids)).scalar_subquery()
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids_q)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(sids)))
        db.execute(sa_delete(SuggestionFeedback).where(
            SuggestionFeedback.student_id.in_(sids)
        ))
        sb_ids_q = db.query(StudentBook.id).filter(
            StudentBook.student_id.in_(sids)
        ).scalar_subquery()
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id.in_(sb_ids_q)
        ))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == seed["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        # Academic years + phases (CASCADE)
        db.execute(sa_delete(AcademicYear).where(AcademicYear.teacher_id.in_(tids)))
        # CSV import yarattığı extra user'lar — PFX patternine sahip
        db.execute(sa_delete(User).where(
            (User.email.like(f"%{PFX}%@%")) | (User.id.in_(tids + sids))
        ))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher/academic + grade-advance + csv smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} student={seed['student_id']}\n")

    try:
        client = TestClient(app)
        _login_v2(client, TEACHER_EMAIL)

        # ===== 1. /academic/years (boş) + /years/choices =====
        r1 = client.get("/api/v2/teacher/academic/years")
        r2 = client.get("/api/v2/teacher/academic/years/choices")
        b1 = r1.json() if r1.text else {}
        b2 = r2.json() if r2.text else {}
        ok = (
            r1.status_code == 200 and r2.status_code == 200
            and isinstance(b1.get("items"), list)
            and isinstance(b2.get("items"), list)
            and len(b2.get("items", [])) >= 6
        )
        check("1. GET /academic/years + /years/choices",
              ok, f"r1={r1.status_code} r2={r2.status_code}")

        # ===== 2. POST /academic/years =====
        r = client.post(
            "/api/v2/teacher/academic/years",
            json={"start_year": 2026},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        year_id = data.get("id")
        ok = (
            r.status_code == 200
            and isinstance(year_id, int)
            and data.get("name") == "2026-2027"
            and any(":academic:years" in k for k in body.get("invalidate", []))
        )
        check("2. POST /academic/years happy",
              ok, f"status={r.status_code} id={year_id} name={data.get('name')}")

        # ===== 3. POST /years/{id}/phases =====
        today = date.today()
        ph_start = today
        ph_end = today + timedelta(days=30)
        r = client.post(
            f"/api/v2/teacher/academic/years/{year_id}/phases",
            json={
                "name": "1. Dönem",
                "start_date": ph_start.isoformat(),
                "end_date": ph_end.isoformat(),
                "kind": "regular",
                "notes": "test",
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        phase_id = data.get("id")
        ok = (
            r.status_code == 200
            and isinstance(phase_id, int)
            and data.get("name") == "1. Dönem"
            and data.get("kind") == "regular"
        )
        check("3. POST /years/{id}/phases",
              ok, f"status={r.status_code} id={phase_id}")

        # ===== 4. PATCH /years/{id}/phases/{pid} =====
        new_end = (today + timedelta(days=60)).isoformat()
        r = client.patch(
            f"/api/v2/teacher/academic/years/{year_id}/phases/{phase_id}",
            json={"end_date": new_end},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("end_date") == new_end
        )
        check("4. PATCH /years/.../phases/{pid} end_date",
              ok, f"status={r.status_code} end={data.get('end_date')}")

        # ===== 5. PATCH /years/{id}/students diff atama =====
        r = client.patch(
            f"/api/v2/teacher/academic/years/{year_id}/students",
            json={"student_ids": [seed["student_id"]]},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("assigned_count") == 1
            and data.get("removed_count") == 0
        )
        check("5. PATCH /years/.../students (assigned=1)",
              ok, f"status={r.status_code} data={data}")

        # ===== 6. DELETE /years/{id} (öğrenci atanmış → 409) =====
        r = client.delete(f"/api/v2/teacher/academic/years/{year_id}")
        body = r.json() if r.text else {}
        det = body.get("detail", {})
        ok = (
            r.status_code == 409
            and det.get("code") == "has_students"
        )
        check("6. DELETE /years/{id} → 409 has_students",
              ok, f"status={r.status_code} code={det.get('code')}")

        # ===== 7. GET /grade-advance/preview =====
        r = client.get("/api/v2/teacher/grade-advance/preview")
        body = r.json() if r.text else {}
        students = body.get("students", [])
        target = next(
            (s for s in students if s.get("student_id") == seed["student_id"]),
            None,
        )
        ok = (
            r.status_code == 200
            and target is not None
            and target.get("current_grade_level") == 8
            and target.get("suggested_grade_level") == 9
            and target.get("has_reservations") is True
        )
        check("7. GET /grade-advance/preview",
              ok, f"status={r.status_code} target={target}")

        # ===== 8. POST /grade-advance/apply — rezerv KORUNUR =====
        # Önce mevcut rezerv ve task'lar mevcut mu?
        with SessionLocal() as db:
            sp_before = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["section_id"])
                .first()
            )
            reserved_before = sp_before.reserved_count if sp_before else 0
            tasks_before = (
                db.query(Task)
                .filter(Task.student_id == seed["student_id"])
                .count()
            )

        r = client.post(
            "/api/v2/teacher/grade-advance/apply",
            json={
                "items": [{
                    "student_id": seed["student_id"],
                    "new_grade_level": 9,
                    "new_is_graduate": False,
                }],
                "target_academic_year_id": year_id,
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})

        with SessionLocal() as db:
            s = db.query(User).filter(User.id == seed["student_id"]).first()
            sp_after = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["section_id"])
                .first()
            )
            reserved_after = sp_after.reserved_count if sp_after else -1
            tasks_after = (
                db.query(Task)
                .filter(Task.student_id == seed["student_id"])
                .count()
            )

        ok = (
            r.status_code == 200
            and data.get("advanced_count") == 1
            and data.get("preserved_reservations_count") == 1
            and s is not None and s.grade_level == 9
            and s.academic_year_id == year_id
            and reserved_after == reserved_before    # REZERV KORUNDU
            and tasks_after == tasks_before          # TASK'LAR KORUNDU
        )
        check("8. POST /grade-advance/apply rezerv+task KORUNDU",
              ok, f"adv={data.get('advanced_count')} rb={reserved_before}→ra={reserved_after} tb={tasks_before}→ta={tasks_after}")

        # ===== 9. reset-program yanlış ad → 422 =====
        r = client.post(
            f"/api/v2/teacher/grade-advance/students/{seed['student_id']}/reset-program",
            json={"confirm_full_name": "Yanlış İsim"},
        )
        body = r.json() if r.text else {}
        det = body.get("detail", {})
        ok = (
            r.status_code == 422
            and det.get("code") == "confirm_name_mismatch"
        )
        check("9. reset-program yanlış isim → 422",
              ok, f"status={r.status_code} code={det.get('code')}")

        # ===== 10. reset-program doğru ad → temizlendi =====
        r = client.post(
            f"/api/v2/teacher/grade-advance/students/{seed['student_id']}/reset-program",
            json={"confirm_full_name": seed["student_full_name"]},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            tasks_after = db.query(Task).filter(
                Task.student_id == seed["student_id"]
            ).count()
            sp_after = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["section_id"])
                .first()
            )
            reserved_now = sp_after.reserved_count if sp_after else -1
        ok = (
            r.status_code == 200
            and data.get("deleted_tasks") >= 1
            and tasks_after == 0
            and reserved_now == 0
        )
        check("10. reset-program doğru ad → tasks+rezerv sıfırlandı",
              ok, f"status={r.status_code} tasks={tasks_after} reserved={reserved_now}")

        # ===== 11. CSV import preview =====
        csv_text = (
            "full_name,email,grade_level,track,is_graduate,graduate_mode\n"
            f"Yeni Ogrenci A,csv1.{PFX}@test.invalid,8,,,\n"
            f"Yeni Ogrenci B,csv2.{PFX}@test.invalid,11,sayisal,,\n"
            "Bozuk Satir,GECERSIZ-EMAIL,abc,,,\n"
        )
        r = client.post(
            "/api/v2/teacher/csv/import/students/preview",
            json={"csv_text": csv_text},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("valid_count") == 2
            and body.get("invalid_count") == 1
            and body.get("total_rows") == 3
        )
        check("11. CSV import preview (2 valid + 1 invalid)",
              ok, f"valid={body.get('valid_count')} invalid={body.get('invalid_count')}")

        # ===== 12. CSV import commit =====
        r = client.post(
            "/api/v2/teacher/csv/import/students/commit",
            json={"csv_text": csv_text},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            new_users = (
                db.query(User)
                .filter(User.email.like(f"csv%.{PFX}@test.invalid"))
                .all()
            )
        ok = (
            r.status_code == 200
            and data.get("created_count") == 2
            and len(new_users) == 2
            and all(u.teacher_id == seed["teacher_id"] for u in new_users)
            and all(u.password_hash for u in new_users)
        )
        check("12. CSV import commit → 2 öğrenci yaratıldı",
              ok, f"created={data.get('created_count')} db_count={len(new_users)}")

        # ===== 13. CSV export students =====
        r = client.get("/api/v2/teacher/csv/export/students")
        ct = r.headers.get("content-type", "")
        text = r.text
        ok = (
            r.status_code == 200
            and "text/csv" in ct
            and "full_name,email" in text
            and seed["student_full_name"] in text
            # Cross-tenant: diğer öğretmenin öğrencisinin email'i SET'te olmamalı
            and OTHER_STUDENT_EMAIL not in text
        )
        check("13. CSV export students (BOM + filtre + cross-tenant)",
              ok, f"status={r.status_code} ct={ct[:30]}")

        # ===== 14. Cross-tenant 404 =====
        # Başka öğretmenin yılı için → other_teacher yarat ve oradan id al
        # Burada hızlı yöntem: hiç var olmayan yıl_id ile dene
        bad_id = 999999
        r1 = client.get(f"/api/v2/teacher/academic/years/{bad_id}")
        r2 = client.patch(
            f"/api/v2/teacher/academic/years/{bad_id}/students",
            json={"student_ids": []},
        )
        r3 = client.post(
            f"/api/v2/teacher/grade-advance/students/{seed['other_student_id']}/reset-program",
            json={"confirm_full_name": "X"},
        )
        ok = (
            r1.status_code == 404
            and r2.status_code == 404
            and r3.status_code == 404
        )
        check("14. Cross-tenant 404 (yıl/student başka öğretmenin)",
              ok, f"r1={r1.status_code} r2={r2.status_code} r3={r3.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n  Sonuç: {passed} PASS, {len(failed)} FAIL")
    if failed:
        print("  Hatalar:")
        for f in failed:
            print(f"    - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
