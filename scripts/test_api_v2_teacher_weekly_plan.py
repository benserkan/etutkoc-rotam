"""API v2 /teacher/students/{id}/week + yardımcı endpoint smoke (Paket 3.5a.1).

Senaryolar (14):
   1. GET /week zenginleştirilmiş (week_anchor, week_draft_total, maturity_*, active_phase, track_*)
   2. GET /week — her gün için subject_summary + suggestions + draft_count alanları
   3. GET /week-notes — boş başlar
   4. POST /week-notes ekle → invalidate prefix var
   5. POST /week-notes/{id}/toggle is_done=True
   6. DELETE /week-notes/{id}
   7. POST /publish-day — taslakları yayına alır + week_draft_total düşer
   8. POST /publish-week — kalan taslakları temizler
   9. POST /tasks/reorder — order alanı güncellenir
  10. POST /program/notify-parents (no_tasks=False senaryosu)
  11. GET /sidebar-items — 3 seviyeli (subject→book→section), sayılar tutarlı
  12. GET /sidebar-items?subject_id=N → filtre çalışır
  13. GET /books-by-subject + /book-sections + /section-stats cascade
  14. Cross-tenant 404 (başka öğretmenin öğrencisinin endpoint'leri)
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
    SuggestionFeedback,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
    WeekNote,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2wp_{secrets.token_hex(3)}"
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
    """2 öğretmen + 2 öğrenci + 1 ders + 1 kitap + 2 bölüm + 1 atama
    + günü taslak ve bir günü canlı görevler (publish-day testi için)."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 WP Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen WP", role=UserRole.TEACHER, is_active=True,
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

        subj = Subject(
            name=f"V2WP Ders {PFX}", order=999,
            is_builtin=False, teacher_id=teacher.id,
        )
        db.add(subj); db.flush()
        book = Book(
            name=f"WP Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book); db.flush()
        sec1 = BookSection(book_id=book.id, label="Bölüm 1", test_count=20, order=0)
        sec2 = BookSection(book_id=book.id, label="Bölüm 2", test_count=15, order=1)
        db.add_all([sec1, sec2]); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()
        sp1 = SectionProgress(
            student_book_id=sb.id, book_section_id=sec1.id,
            reserved_count=2, completed_count=3,
        )
        sp2 = SectionProgress(
            student_book_id=sb.id, book_section_id=sec2.id,
            reserved_count=0, completed_count=0,
        )
        db.add_all([sp1, sp2])

        today = date.today()
        # Bugün için 2 taslak + 1 canlı görev
        t_draft1 = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Taslak 1", status=TaskStatus.PENDING, order=0, is_draft=True,
        )
        t_draft2 = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Taslak 2", status=TaskStatus.PENDING, order=1, is_draft=True,
        )
        t_live = Task(
            student_id=student.id, date=today, type=TaskType.TEST,
            title="Canlı görev", status=TaskStatus.PENDING, order=2, is_draft=False,
        )
        db.add_all([t_draft1, t_draft2, t_live]); db.flush()
        db.add_all([
            TaskBookItem(task_id=t_draft1.id, book_id=book.id, book_section_id=sec1.id,
                         planned_count=2, completed_count=0),
            TaskBookItem(task_id=t_draft2.id, book_id=book.id, book_section_id=sec2.id,
                         planned_count=3, completed_count=0),
            TaskBookItem(task_id=t_live.id, book_id=book.id, book_section_id=sec1.id,
                         planned_count=1, completed_count=1),
        ])

        # Yarın için 1 ek taslak (publish-week testinde temizlenmesi gereken)
        t_tomorrow = Task(
            student_id=student.id, date=today + timedelta(days=1),
            type=TaskType.TEST, title="Yarın taslak",
            status=TaskStatus.PENDING, order=0, is_draft=True,
        )
        db.add(t_tomorrow); db.flush()
        db.add(TaskBookItem(
            task_id=t_tomorrow.id, book_id=book.id, book_section_id=sec1.id,
            planned_count=1, completed_count=0,
        ))

        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "subject_id": subj.id,
            "book_id": book.id,
            "section1_id": sec1.id,
            "section2_id": sec2.id,
            "today": today,
            "task_ids_today": [t_draft1.id, t_draft2.id, t_live.id],
            "task_id_tomorrow": t_tomorrow.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        sids = [seed["student_id"], seed["other_student_id"]]
        # Notes
        db.execute(sa_delete(WeekNote).where(WeekNote.student_id.in_(sids)))
        # Tasks
        task_ids_q = db.query(Task.id).filter(Task.student_id.in_(sids)).scalar_subquery()
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids_q)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(sids)))
        db.execute(sa_delete(SuggestionFeedback).where(SuggestionFeedback.student_id.in_(sids)))
        # Books / sections
        sb_ids_q = db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids)).scalar_subquery()
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sb_ids_q)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == seed["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["teacher_id"], seed["other_teacher_id"],
            seed["student_id"], seed["other_student_id"],
        ])))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher weekly-plan smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} student={seed['student_id']}\n")

    today = seed["today"]
    tomorrow = today + timedelta(days=1)

    try:
        client = TestClient(app)
        _login(client, TEACHER_EMAIL)

        # ===== 1. /week zenginleştirilmiş yanıt =====
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/week")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and "week_anchor" in body
            and "week_draft_total" in body
            and "maturity_value" in body
            and "maturity_label" in body
            and "track_required" in body
            and body.get("week_draft_total") == 3  # 2 bugün + 1 yarın
            and isinstance(body.get("days"), list) and len(body["days"]) == 7
        )
        check("1. GET /week zenginleştirilmiş alanlar",
              ok, f"status={r.status_code} draft_total={body.get('week_draft_total')}")

        # ===== 2. /week her gün için subject_summary + suggestions + draft_count =====
        days = body.get("days", [])
        today_day = next((d for d in days if d.get("date") == today.isoformat()), None)
        ok = (
            today_day is not None
            and "subject_summary" in today_day
            and "suggestions" in today_day
            and today_day.get("draft_count") == 2
            and isinstance(today_day.get("subject_summary"), list)
        )
        check("2. /week.days[].subject_summary + suggestions + draft_count",
              ok, f"today={today_day and today_day.get('draft_count')} sub={today_day and len(today_day.get('subject_summary', []))}")

        # ===== 3. /week-notes boş başlar =====
        r = client.get(
            f"/api/v2/teacher/students/{seed['student_id']}/week-notes?week_start={today.isoformat()}"
        )
        ok = (r.status_code == 200 and r.json() == [])
        check("3. GET /week-notes boş başlar",
              ok, f"status={r.status_code}")

        # ===== 4. POST /week-notes ekle =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/week-notes",
            json={"week_start": today.isoformat(), "body": "Pazartesi dersine TYT denemesi getir"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        note_id = data.get("id")
        ok = (
            r.status_code == 200
            and isinstance(note_id, int)
            and data.get("body", "").startswith("Pazartesi")
            and any(":notes" in k or ":week" in k for k in body.get("invalidate", []))
        )
        check("4. POST /week-notes (invalidate prefix var)",
              ok, f"status={r.status_code} id={note_id}")

        # ===== 5. POST /week-notes/{id}/toggle =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/week-notes/{note_id}/toggle"
        )
        data = (r.json() or {}).get("data", {})
        ok = (r.status_code == 200 and data.get("is_done") is True)
        check("5. POST /week-notes/{id}/toggle is_done=True",
              ok, f"status={r.status_code} is_done={data.get('is_done')}")

        # ===== 6. DELETE /week-notes/{id} =====
        r = client.delete(
            f"/api/v2/teacher/students/{seed['student_id']}/week-notes/{note_id}"
        )
        data = (r.json() or {}).get("data", {})
        ok = (r.status_code == 200 and data.get("deleted") is True)
        check("6. DELETE /week-notes/{id}",
              ok, f"status={r.status_code}")

        # ===== 7. POST /publish-day — taslakları yayına al =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/publish-day",
            json={"task_date": today.isoformat()},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            today_drafts = (
                db.query(Task)
                .filter(
                    Task.student_id == seed["student_id"],
                    Task.date == today,
                    Task.is_draft.is_(True),
                )
                .count()
            )
        ok = (
            r.status_code == 200
            and data.get("published_count") == 2
            and today_drafts == 0
        )
        check("7. POST /publish-day → bugün taslak=0",
              ok, f"published={data.get('published_count')} db_drafts={today_drafts}")

        # ===== 8. POST /publish-week — kalan taslakları temizle =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/publish-week",
            json={"week_start": today.isoformat()},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            remaining_drafts = (
                db.query(Task)
                .filter(
                    Task.student_id == seed["student_id"],
                    Task.is_draft.is_(True),
                )
                .count()
            )
        ok = (
            r.status_code == 200
            and data.get("published_count") >= 1
            and data.get("week_draft_total") == 0
            and remaining_drafts == 0
        )
        check("8. POST /publish-week → tüm taslaklar temizlendi",
              ok, f"published={data.get('published_count')} remaining={remaining_drafts}")

        # ===== 9. POST /tasks/reorder =====
        # task_ids sırası: live, draft1(artık canlı), draft2(canlı) (3 görev)
        ids_for_today = list(reversed(seed["task_ids_today"]))
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/tasks/reorder",
            json={"task_date": today.isoformat(), "task_ids": ids_for_today},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        with SessionLocal() as db:
            first = (
                db.query(Task)
                .filter(Task.id == ids_for_today[0])
                .first()
            )
        ok = (
            r.status_code == 200
            and data.get("reordered_count", 0) >= 1
            and first is not None and first.order == 0
        )
        check("9. POST /tasks/reorder",
              ok, f"reordered={data.get('reordered_count')} first_order={first and first.order}")

        # ===== 10. POST /program/notify-parents (görevli hafta) =====
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/program/notify-parents",
            json={"week_start": today.isoformat()},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and "fired" in data
            and "no_tasks" in data
            and len(data.get("message", "")) > 0
        )
        check("10. POST /program/notify-parents",
              ok, f"fired={data.get('fired')} no_tasks={data.get('no_tasks')}")

        # ===== 11. GET /sidebar-items — 3 seviyeli =====
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/sidebar-items")
        body = r.json() if r.text else {}
        subjects = body.get("subjects", [])
        target_subj = next((s for s in subjects if s.get("id") == seed["subject_id"]), None)
        target_book = (
            target_subj and next(
                (b for b in target_subj.get("books", []) if b.get("id") == seed["book_id"]),
                None,
            )
        )
        ok = (
            r.status_code == 200
            and target_subj is not None
            and target_book is not None
            and len(target_book.get("sections", [])) == 2
            and target_book["sections"][0].get("total") == 20
            and target_book["sections"][1].get("total") == 15
            and target_book.get("total") == 35
        )
        check("11. GET /sidebar-items 3 seviye (subject→book→section)",
              ok, f"status={r.status_code} sub={target_subj and target_subj.get('id')} book_total={target_book and target_book.get('total')}")

        # ===== 12. /sidebar-items?subject_id= filtre =====
        r = client.get(
            f"/api/v2/teacher/students/{seed['student_id']}/sidebar-items?subject_id={seed['subject_id']}"
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("focused_subject_id") == seed["subject_id"]
            and len(body.get("subjects", [])) == 1
        )
        check("12. /sidebar-items?subject_id= filtre",
              ok, f"focused={body.get('focused_subject_id')} subs={len(body.get('subjects', []))}")

        # ===== 13. cascade: books-by-subject + book-sections + section-stats =====
        r1 = client.get(
            f"/api/v2/teacher/students/{seed['student_id']}/books-by-subject?subject_id={seed['subject_id']}"
        )
        b1 = r1.json() if r1.text else {}
        r2 = client.get(
            f"/api/v2/teacher/students/{seed['student_id']}/book-sections?book_id={seed['book_id']}"
        )
        b2 = r2.json() if r2.text else {}
        r3 = client.get(
            f"/api/v2/teacher/students/{seed['student_id']}/section-stats?section_id={seed['section1_id']}"
        )
        b3 = r3.json() if r3.text else {}
        ok = (
            r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 200
            and len(b1.get("items", [])) == 1
            and b1["items"][0].get("id") == seed["book_id"]
            and len(b2.get("items", [])) == 2
            and b3.get("section_id") == seed["section1_id"]
            and b3.get("total") == 20
            and b3.get("completed") >= 0
        )
        check("13. Cascade books-by-subject + book-sections + section-stats",
              ok, f"r1={r1.status_code}/{len(b1.get('items', []))} r2={r2.status_code}/{len(b2.get('items', []))} r3={r3.status_code}")

        # ===== 14. Cross-tenant 404 =====
        r1 = client.get(
            f"/api/v2/teacher/students/{seed['other_student_id']}/sidebar-items"
        )
        r2 = client.post(
            f"/api/v2/teacher/students/{seed['other_student_id']}/week-notes",
            json={"week_start": today.isoformat(), "body": "test"},
        )
        r3 = client.post(
            f"/api/v2/teacher/students/{seed['other_student_id']}/publish-day",
            json={"task_date": today.isoformat()},
        )
        ok = (r1.status_code == 404 and r2.status_code == 404 and r3.status_code == 404)
        check("14. Cross-tenant 404",
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
