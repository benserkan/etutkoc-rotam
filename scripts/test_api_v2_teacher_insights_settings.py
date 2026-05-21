"""API v2 /teacher/insights + /teacher/settings + /teacher/usage smoke (Dalga 3 Paket 9).

Senaryolar (12):
   1. GET /insights/overview → fleet özet + sağlık badge'leri
   2. POST /insights/students/{id}/suggestions/accept → task yarattı + invalidate
   3. POST /insights/students/{id}/suggestions/reject → SuggestionFeedback REJECTED kaydı
   4. POST /insights/students/{id}/suggestions/accept-all → toplu + errors[]
   5. GET /insights/students/{id}/suggestions?date=... → panel (boş set kabul)
   6. GET /insights/students/{id}/diagnostics → pattern/volume/reject + maturity
   7. GET /insights/students/{id}/suggestions/ahead → 7 gün bundle
   8. GET /teacher/settings → email_config + cron_schedules + profile
   9. PATCH /teacher/settings/cron/{id} hour=8 minute=15 enabled=true → güncellendi
  10. POST /teacher/settings/test-email → sent=False (SMTP yok) + message net
  11. GET /teacher/usage/current bağımsız → account + breakdown + plan_allocations
  12. Cross-tenant 404 (başka öğretmenin öğrencisinin suggestions/diagnostics)
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
    CronSchedule,
    FeedbackAction,
    SectionProgress,
    StudentBook,
    Subject,
    SuggestionFeedback,
    Task,
    TaskBookItem,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2ins_{secrets.token_hex(3)}"
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
    """2 öğretmen + 2 öğrenci (her birine bir tane) + 1 kitap + 1 bölüm + bir cron schedule."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Ins Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen Ins", role=UserRole.TEACHER, is_active=True,
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
            name=f"V2Ins Ders {PFX}", order=999,
            is_builtin=False, teacher_id=teacher.id,
        )
        db.add(subj)
        db.flush()
        book = Book(
            name=f"Test Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=teacher.id,
        )
        db.add(book)
        db.flush()
        section = BookSection(
            book_id=book.id, label="Bölüm 1", test_count=20, order=0,
        )
        db.add(section)
        db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb)
        db.flush()
        sp = SectionProgress(
            student_book_id=sb.id, book_section_id=section.id,
            reserved_count=0, completed_count=0,
        )
        db.add(sp)

        # Cron schedule kaydı — PATCH ve list için
        cron = CronSchedule(
            job_key=f"daily_summary_{PFX}", description="Test cron",
            hour=18, minute=0, day_of_week=None, enabled=True,
        )
        db.add(cron)
        db.commit()

        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "subject_id": subj.id,
            "book_id": book.id,
            "section_id": section.id,
            "student_book_id": sb.id,
            "cron_id": cron.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        ids = [seed["student_id"], seed["other_student_id"]]
        # Tasks + TaskBookItem (CASCADE FK ondelete=CASCADE varsayım; defansif sil)
        task_ids_q = db.query(Task.id).filter(Task.student_id.in_(ids)).scalar_subquery()
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids_q)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(SuggestionFeedback).where(SuggestionFeedback.student_id.in_(ids)))
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id.in_(
                db.query(StudentBook.id).filter(StudentBook.student_id.in_(ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == seed["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(CronSchedule).where(CronSchedule.id == seed["cron_id"]))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["teacher_id"], seed["other_teacher_id"],
            seed["student_id"], seed["other_student_id"],
        ])))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher/insights + /settings smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} student={seed['student_id']}\n")

    today = date.today()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    try:
        client = TestClient(app)
        _login_v2(client, TEACHER_EMAIL)

        # ===== 1. GET /insights/overview =====
        r = client.get("/api/v2/teacher/insights/overview")
        body = r.json() if r.text else {}
        students = body.get("students", [])
        ok = (
            r.status_code == 200
            and body.get("teacher_id") == seed["teacher_id"]
            and any(s.get("student_id") == seed["student_id"] for s in students)
            and isinstance(body.get("health_overall"), dict)
            and isinstance(body.get("health_activity"), dict)
            and isinstance(body.get("weekly_trend"), list)
        )
        check("1. GET /insights/overview",
              ok, f"status={r.status_code} students={len(students)}")

        # ===== 2. POST accept tek öneri =====
        r = client.post(
            f"/api/v2/teacher/insights/students/{seed['student_id']}/suggestions/accept",
            json={
                "date": tomorrow.isoformat(),
                "book_id": seed["book_id"],
                "section_id": seed["section_id"],
                "planned_count": 3,
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        task_id_1 = data.get("task_id")
        with SessionLocal() as db:
            tb = (
                db.query(TaskBookItem)
                .filter(TaskBookItem.task_id == task_id_1)
                .first()
            )
            tb_ok = bool(tb and tb.planned_count == 3)
            sp = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == seed["section_id"])
                .first()
            )
            reserved_after = sp.reserved_count if sp else 0
        ok = (
            r.status_code == 200
            and data.get("accepted") is True
            and isinstance(task_id_1, int)
            and tb_ok
            and reserved_after >= 3
            and any("insights" in k for k in body.get("invalidate", []))
        )
        check("2. POST accept → task + rezerv",
              ok, f"status={r.status_code} task={task_id_1} reserved={reserved_after}")

        # ===== 3. POST reject =====
        r = client.post(
            f"/api/v2/teacher/insights/students/{seed['student_id']}/suggestions/reject",
            json={
                "date": tomorrow.isoformat(),
                "book_id": seed["book_id"],
                "section_id": seed["section_id"],
            },
        )
        body = r.json() if r.text else {}
        with SessionLocal() as db:
            fb = (
                db.query(SuggestionFeedback)
                .filter(
                    SuggestionFeedback.student_id == seed["student_id"],
                    SuggestionFeedback.book_id == seed["book_id"],
                    SuggestionFeedback.book_section_id == seed["section_id"],
                    SuggestionFeedback.action == FeedbackAction.REJECTED,
                )
                .first()
            )
            fb_ok = bool(fb and fb.count >= 1)
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("rejected") is True
            and fb_ok
        )
        check("3. POST reject → SuggestionFeedback REJECTED",
              ok, f"status={r.status_code} fb={fb_ok}")

        # ===== 4. POST accept-all =====
        # day_after için 2 kez ekleyelim — biri valid, biri planned_count=0 (skip)
        r = client.post(
            f"/api/v2/teacher/insights/students/{seed['student_id']}/suggestions/accept-all",
            json={
                "date": day_after.isoformat(),
                "items": [
                    {"book_id": seed["book_id"], "section_id": seed["section_id"], "planned_count": 2},
                    {"book_id": seed["book_id"], "section_id": seed["section_id"], "planned_count": 0},
                ],
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("created_count") == 1
            and len(data.get("errors", [])) >= 1
        )
        check("4. POST accept-all → 1 oluştu + 1 hata",
              ok, f"status={r.status_code} data={data}")

        # ===== 5. GET suggestions panel =====
        r = client.get(
            f"/api/v2/teacher/insights/students/{seed['student_id']}/suggestions?date={tomorrow.isoformat()}"
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("target_date") == tomorrow.isoformat()
            and "suggestions" in body
            and isinstance(body.get("suggestions"), list)
            and "maturity_value" in body
        )
        check("5. GET /insights/.../suggestions?date=...",
              ok, f"status={r.status_code} keys={list(body.keys())}")

        # ===== 6. GET diagnostics =====
        r = client.get(
            f"/api/v2/teacher/insights/students/{seed['student_id']}/diagnostics"
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("student", {}).get("id") == seed["student_id"]
            and "pattern_rows" in body and "volume_rows" in body and "reject_rows" in body
            and body.get("maturity_weeks_constant") == 8
            and len(body.get("volume_rows", [])) == 7
        )
        check("6. GET /insights/.../diagnostics",
              ok, f"status={r.status_code} volume_rows={len(body.get('volume_rows', []))}")

        # ===== 7. GET suggestions/ahead =====
        r = client.get(
            f"/api/v2/teacher/insights/students/{seed['student_id']}/suggestions/ahead"
        )
        body = r.json() if r.text else {}
        days = body.get("days", [])
        ok = (
            r.status_code == 200
            and len(days) == 7
            and days[0].get("date") == today.isoformat()
        )
        check("7. GET /insights/.../suggestions/ahead 7-gün",
              ok, f"status={r.status_code} days={len(days)}")

        # ===== 8. GET /teacher/settings =====
        r = client.get("/api/v2/teacher/settings")
        body = r.json() if r.text else {}
        crons = body.get("cron_schedules", [])
        ok = (
            r.status_code == 200
            and body.get("teacher", {}).get("id") == seed["teacher_id"]
            and isinstance(body.get("email_config"), dict)
            and any(c.get("id") == seed["cron_id"] for c in crons)
        )
        check("8. GET /teacher/settings",
              ok, f"status={r.status_code} crons={len(crons)}")

        # ===== 9. PATCH /teacher/settings/cron/{id} =====
        r = client.patch(
            f"/api/v2/teacher/settings/cron/{seed['cron_id']}",
            json={"hour": 8, "minute": 15, "enabled": True, "day_of_week": 0},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("hour") == 8
            and data.get("minute") == 15
            and data.get("day_of_week") == 0
            and data.get("enabled") is True
            and any(":settings" in k for k in body.get("invalidate", []))
        )
        check("9. PATCH /teacher/settings/cron/{id}",
              ok, f"status={r.status_code} data={data}")

        # ===== 10. POST test-email — SMTP yok → sent=False ama message net =====
        r = client.post(
            "/api/v2/teacher/settings/test-email",
            json={"to": "demo@test.invalid"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("to") == "demo@test.invalid"
            and isinstance(data.get("sent"), bool)
            and len(data.get("message", "")) > 0
        )
        check("10. POST /teacher/settings/test-email",
              ok, f"status={r.status_code} sent={data.get('sent')} msg={data.get('message', '')[:40]}")

        # ===== 11. GET /teacher/usage/current bağımsız =====
        r = client.get("/api/v2/teacher/usage/current")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("is_independent") is True
            and isinstance(body.get("account"), dict)
            and isinstance(body.get("plan_allocations"), list)
            and len(body.get("plan_allocations", [])) >= 1
            and isinstance(body.get("kind_costs"), list)
        )
        check("11. GET /teacher/usage/current (bağımsız öğretmen)",
              ok, f"status={r.status_code} keys={list(body.keys())[:6]}")

        # ===== 12. Cross-tenant 404 =====
        # other_student başka öğretmenin → 404
        r1 = client.get(
            f"/api/v2/teacher/insights/students/{seed['other_student_id']}/diagnostics"
        )
        r2 = client.post(
            f"/api/v2/teacher/insights/students/{seed['other_student_id']}/suggestions/accept",
            json={
                "date": tomorrow.isoformat(),
                "book_id": seed["book_id"],
                "section_id": seed["section_id"],
                "planned_count": 1,
            },
        )
        r3 = client.get(
            f"/api/v2/teacher/insights/students/{seed['other_student_id']}/suggestions?date={tomorrow.isoformat()}"
        )
        ok = (r1.status_code == 404 and r2.status_code == 404 and r3.status_code == 404)
        check("12. Cross-tenant 404 (başka öğretmenin öğrencisi)",
              ok, f"diag={r1.status_code} accept={r2.status_code} panel={r3.status_code}")

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
