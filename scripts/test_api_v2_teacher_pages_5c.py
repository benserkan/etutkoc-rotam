"""API v2 öğretmen paneli 5c smoke (promote / focus / dna / review / goals).

Senaryolar (18):
   1. GET /promote-form happy
   2. POST /promote 11. sınıf track yok → 422 track_required
   3. POST /promote 11 + sayisal → 200 + müfredat_label dolu
   4. POST /promote mezun + full_time → 200 + graduate_mode korunur
   5. POST /promote başkasının → 404
   6. GET /focus happy (read-only)
   7. GET /focus başkasının → 404
   8. GET /dna happy + heatmap 7×24
   9. POST /dna/notify-parent veli yok → 422 no_active_parents
  10. GET /review happy + breakdown + subjects (curriculum filtreli)
  11. POST /review/seed happy + idempotent
  12. POST /review/seed başkasının subject → 404
  13. GET /goals happy + subjects[] + roots[]
  14. POST /goals create happy
  15. POST /goals create boş title → 422 invalid_title
  16. POST /goals create geçersiz date → 422 invalid_date
  17. POST /goals/{id}/achieve → status=achieved
  18. DELETE /goals/{id} → deleted=True
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
    GoalKind,
    ReviewCard,
    StudentBook,
    StudentGoal,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2_5c_{secrets.token_hex(3)}"
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
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 5c Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen 5c", role=UserRole.TEACHER, is_active=True,
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

        # Subject + Topic + Book + Section (review seed için)
        subj = Subject(
            name=f"V2 5c Ders {PFX}", order=999,
            is_builtin=False, teacher_id=teacher.id,
        )
        # Başka öğretmenin subject'i — cross-tenant seed testi için
        other_subj = Subject(
            name=f"Diğer Ders {PFX}", order=998,
            is_builtin=False, teacher_id=other_teacher.id,
        )
        db.add_all([subj, other_subj]); db.flush()

        topic = Topic(
            subject_id=subj.id, name=f"Konu {PFX}", order=0,
            is_builtin=False, teacher_id=teacher.id,
        )
        db.add(topic); db.flush()

        book = Book(
            name=f"5c Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()
        sec1 = BookSection(
            book_id=book.id, label="Bölüm 1", test_count=10, order=0,
            topic_id=topic.id,
        )
        db.add(sec1); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()

        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "subject_id": subj.id,
            "other_subject_id": other_subj.id,
            "topic_id": topic.id,
            "book_id": book.id,
            "section_id": sec1.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        sids = [seed["student_id"], seed["other_student_id"]]
        # Goals
        db.execute(sa_delete(StudentGoal).where(StudentGoal.student_id.in_(sids)))
        # Review cards
        db.execute(sa_delete(ReviewCard).where(ReviewCard.student_id.in_(sids)))
        # Books
        sb_ids_q = db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids)).scalar_subquery()
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == seed["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(
            Subject.id.in_([seed["subject_id"], seed["other_subject_id"]])
        ))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["teacher_id"], seed["other_teacher_id"],
            seed["student_id"], seed["other_student_id"],
        ])))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher 5c (promote/focus/dna/review/goals) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} student={seed['student_id']}\n")

    try:
        client = TestClient(app)
        _login(client, TEACHER_EMAIL)

        # ============ PROMOTE ============
        # 1) GET promote-form
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/promote-form")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("student_id") == seed["student_id"]
            and isinstance(body.get("grade_choices"), list) and len(body["grade_choices"]) == 9
            and isinstance(body.get("track_choices"), list) and len(body["track_choices"]) == 4
            and body.get("maarif_first_grade9_year") == 2024
        )
        check("1. GET /promote-form happy", ok, f"status={r.status_code}")

        # 2) 11. sınıf track yok → 422
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/promote",
            json={"grade": "11"},
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "track_required"
        )
        check("2. POST /promote 11. sınıf track yok → 422 track_required",
              ok, f"status={r.status_code}")

        # 3) 11 + sayisal → 200
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/promote",
            json={"grade": "11", "track": "sayisal"},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("new_grade_label", "").startswith("11")
            and body.get("data", {}).get("new_track_label") is not None
        )
        check("3. POST /promote 11 + sayisal → 200",
              ok, f"status={r.status_code} body={body}")

        # 4) Mezun + full_time
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/promote",
            json={"grade": "graduate", "track": "ea", "graduate_mode": "full_time"},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("new_graduate_mode_label") is not None
        )
        check("4. POST /promote mezun + full_time", ok, f"status={r.status_code}")

        # 5) Başkasının öğrencisi → 404
        r = client.post(
            f"/api/v2/teacher/students/{seed['other_student_id']}/promote",
            json={"grade": "9"},
        )
        ok = r.status_code == 404
        check("5. POST /promote başkasının → 404", ok, f"status={r.status_code}")

        # Öğrenciyi 8. sınıfa geri al (sonraki testler için)
        client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/promote",
            json={"grade": "8"},
        )

        # ============ FOCUS ============
        # 6) GET focus
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/focus")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and "today_work_sessions" in body
            and "badges" in body and isinstance(body["badges"], list)
            and "recent_sessions" in body and isinstance(body["recent_sessions"], list)
        )
        check("6. GET /focus happy (read-only)", ok, f"status={r.status_code}")

        # 7) Başkasının → 404
        r = client.get(f"/api/v2/teacher/students/{seed['other_student_id']}/focus")
        ok = r.status_code == 404
        check("7. GET /focus başkasının → 404", ok, f"status={r.status_code}")

        # ============ DNA ============
        # 8) GET dna
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/dna")
        body = r.json() if r.text else {}
        heat = body.get("heatmap")
        ok = (
            r.status_code == 200
            and isinstance(heat, list) and len(heat) == 7
            and all(isinstance(row, list) and len(row) == 24 for row in heat)
            and "burnout_risk_score" in body
            and "parent_count" in body
            and "parent_message_preview" in body
        )
        check("8. GET /dna happy + heatmap 7×24", ok, f"status={r.status_code}")

        # 9) Notify-parent veli yok
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/dna/notify-parent",
            json={"body": "Test mesajı"},
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "no_active_parents"
        )
        check("9. POST /dna/notify-parent veli yok → 422", ok, f"status={r.status_code}")

        # ============ REVIEW ============
        # 10) GET review
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/review")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and "breakdown" in body
            and isinstance(body.get("subjects"), list)
            and isinstance(body.get("cards"), list)
            and isinstance(body.get("struggle_cards"), list)
        )
        check("10. GET /review happy + breakdown + subjects",
              ok, f"status={r.status_code}")

        # 11) Review seed (idempotent)
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/review/seed",
            json={"subject_id": seed["subject_id"]},
        )
        body = r.json() if r.text else {}
        added_first = body.get("data", {}).get("added", 0)
        ok = r.status_code == 200 and added_first >= 1
        check("11a. POST /review/seed happy (added>=1)",
              ok, f"status={r.status_code} added={added_first}")

        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/review/seed",
            json={"subject_id": seed["subject_id"]},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("added", -1) == 0
            and body.get("data", {}).get("skipped_existing", 0) >= 1
        )
        check("11b. POST /review/seed idempotent (added=0, skipped>=1)",
              ok, f"status={r.status_code}")

        # 12) Başkasının subject
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/review/seed",
            json={"subject_id": seed["other_subject_id"]},
        )
        ok = r.status_code == 404
        check("12. POST /review/seed başkasının subject → 404",
              ok, f"status={r.status_code}")

        # ============ GOALS ============
        # 13) GET goals
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/goals")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and "subjects" in body
            and "roots" in body
            and "summary" in body
            and "kind_options" in body and isinstance(body["kind_options"], list)
        )
        check("13. GET /goals happy", ok, f"status={r.status_code}")

        # 14) Goal create happy
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/goals",
            json={"title": "Bu hafta 50 test", "kind": "weekly",
                  "target_value": 50, "current_value": 0, "unit": "test"},
        )
        body = r.json() if r.text else {}
        goal_id = body.get("data", {}).get("id")
        ok = r.status_code == 200 and isinstance(goal_id, int)
        check("14. POST /goals create happy", ok, f"status={r.status_code}")

        # 15) Boş title
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/goals",
            json={"title": "  ", "kind": "custom"},
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "invalid_title"
        )
        check("15. POST /goals boş title → 422", ok, f"status={r.status_code}")

        # 16) Geçersiz date
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/goals",
            json={"title": "Test", "kind": "custom", "target_date": "31-12-2026"},
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "invalid_date"
        )
        check("16. POST /goals geçersiz date → 422",
              ok, f"status={r.status_code}")

        # 17) Achieve
        r = client.post(f"/api/v2/teacher/goals/{goal_id}/achieve")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("status") == "achieved"
        )
        check("17. POST /goals/{id}/achieve",
              ok, f"status={r.status_code}")

        # 18) Delete
        r = client.delete(f"/api/v2/teacher/goals/{goal_id}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("deleted") is True
        )
        check("18. DELETE /goals/{id}", ok, f"status={r.status_code}")

    finally:
        _cleanup(seed)
        print(f"\n  cleanup OK\n")

    print(f"\n=== SONUÇ: {passed}/{passed + len(failed)} PASS ===")
    if failed:
        print("\nBaşarısız:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
