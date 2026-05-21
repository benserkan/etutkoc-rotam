"""API v2 /teacher/* salt okunur smoke (Dalga 3 Paket 1).

Senaryolar (12):
   1. /teacher/dashboard happy → fleet özeti + KPI + top_5_at_risk
   2. /teacher/dashboard recent_requests yalnız bekleyen (PENDING) + sahip
   3. /teacher/students liste happy → en az 2 öğrenci, sayfalama meta
   4. /teacher/students filtre q=ad → arama isabetli
   5. /teacher/students filtre grade_level=8 → sadece 8. sınıf
   6. /teacher/students sayfalama page=2, page_size=1 → has_next mantıklı
   7. /teacher/students/{id} kendi öğrencisi → 200, program_summary
   8. /teacher/students/{id} başkasının öğrencisi (diğer öğretmen) → 404
   9. /teacher/students/{id} olmayan id → 404
  10. /teacher/badges polling → pending + at_risk sayım + checked_at
  11. /teacher/me → student_count + active_student_count
  12. Öğrenci kullanıcısı /teacher/dashboard'a vurursa → 403 role_required

Test verisi: secrets prefix; gerçek hesaplara dokunulmaz.
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
    RequestStatus,
    RequestType,
    Task,
    TaskBookItem,
    TaskRequest,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2tr_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_A_EMAIL = f"{PFX}_a@test.invalid"        # 8. sınıf, bizim öğrencimiz
STUDENT_B_EMAIL = f"{PFX}_b@test.invalid"        # 9. sınıf, bizim öğrencimiz
OTHER_STUDENT_EMAIL = f"{PFX}_o@test.invalid"    # diğer öğretmenin öğrencisi
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
    """Test verisi: 2 öğretmen + 3 öğrenci + 2 görev + 1 PENDING talep."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Teach Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        db.add_all([teacher, other_teacher]); db.flush()

        student_a = User(
            email=STUDENT_A_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Ahmet {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=teacher.id,
        )
        student_b = User(
            email=STUDENT_B_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Berke {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=9, teacher_id=teacher.id,
        )
        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Cem {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=other_teacher.id,
        )
        db.add_all([student_a, student_b, other_student]); db.flush()

        # student_a için bugünlük basit bir görev (planned=2, completed=0)
        today = date.today()
        task_a = Task(
            student_id=student_a.id, date=today, type=TaskType.TEST,
            title="Smoke için bugün görevi", status=TaskStatus.PENDING, order=0,
        )
        db.add(task_a); db.flush()

        # student_b'den PENDING bir talep (dashboard.recent_requests için)
        req = TaskRequest(
            student_id=student_b.id, teacher_id=teacher.id,
            task_id=None, type=RequestType.QUESTION,
            status=RequestStatus.PENDING, message="Smoke pending request",
        )
        db.add(req); db.flush()

        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_a_id": student_a.id,
            "student_b_id": student_b.id,
            "other_student_id": other_student.id,
            "task_a_id": task_a.id,
            "request_id": req.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        student_ids = [seed["student_a_id"], seed["student_b_id"], seed["other_student_id"]]
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id.in_(student_ids)))
        # Task'ları student üzerinden topla + temizle
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_(
                db.query(Task.id).filter(Task.student_id.in_(student_ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(Task).where(Task.student_id.in_(student_ids)))
        db.execute(sa_delete(User).where(User.id.in_(
            student_ids + [seed["teacher_id"], seed["other_teacher_id"]]
        )))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher read smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} students={seed['student_a_id']},{seed['student_b_id']}\n")

    try:
        client = TestClient(app)
        _login_v2(client, TEACHER_EMAIL)

        # ===== 1. /dashboard happy =====
        r = client.get("/api/v2/teacher/dashboard")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("student_count", 0) >= 2
            and "fleet_red" in body and "fleet_amber" in body and "fleet_green" in body
            and isinstance(body.get("top_5_at_risk"), list)
            and isinstance(body.get("recent_requests"), list)
        )
        check(
            "1. /dashboard happy",
            ok,
            f"status={r.status_code} student_count={body.get('student_count')} keys={list(body.keys())[:8]}",
        )

        # ===== 2. /dashboard recent_requests sadece bekleyen + sahip =====
        body = r.json()
        recents = body.get("recent_requests", [])
        ok = (
            len(recents) >= 1
            and all(req.get("student_id") in (seed["student_a_id"], seed["student_b_id"]) for req in recents)
        )
        check(
            "2. /dashboard recent_requests sadece sahip",
            ok,
            f"recent={len(recents)} ids={[r.get('student_id') for r in recents]}",
        )

        # ===== 3. /students liste happy =====
        r = client.get("/api/v2/teacher/students")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and len(items) >= 2
            and body.get("page") == 1
            and body.get("total", 0) >= 2
            and all(s.get("id") in (seed["student_a_id"], seed["student_b_id"]) for s in items)
        )
        check(
            "3. /students liste happy",
            ok,
            f"status={r.status_code} items={len(items)} total={body.get('total')}",
        )

        # ===== 4. /students filtre q (ad arama) =====
        r = client.get("/api/v2/teacher/students?q=Ahmet")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and len(items) == 1
            and items[0]["id"] == seed["student_a_id"]
        )
        check(
            "4. /students q=Ahmet",
            ok,
            f"status={r.status_code} count={len(items)} first={items[0].get('full_name') if items else '-'}",
        )

        # ===== 5. /students filtre grade_level=8 =====
        r = client.get("/api/v2/teacher/students?grade_level=8")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and len(items) == 1
            and items[0]["id"] == seed["student_a_id"]
            and items[0]["grade_level"] == 8
        )
        check(
            "5. /students grade_level=8",
            ok,
            f"status={r.status_code} count={len(items)}",
        )

        # ===== 6. /students sayfalama page=2 page_size=1 =====
        r1 = client.get("/api/v2/teacher/students?page=1&page_size=1")
        r2 = client.get("/api/v2/teacher/students?page=2&page_size=1")
        b1, b2 = r1.json(), r2.json()
        ok = (
            r1.status_code == 200 and r2.status_code == 200
            and b1.get("has_next") is True
            and b2.get("has_next") is False
            and len(b1.get("items", [])) == 1
            and len(b2.get("items", [])) == 1
            and b1["items"][0]["id"] != b2["items"][0]["id"]
        )
        check(
            "6. /students sayfalama",
            ok,
            f"p1.has_next={b1.get('has_next')} p2.has_next={b2.get('has_next')} ids={b1['items'][0]['id']}/{b2['items'][0]['id']}",
        )

        # ===== 7. /students/{id} kendi öğrencisi =====
        r = client.get(f"/api/v2/teacher/students/{seed['student_a_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("student", {}).get("id") == seed["student_a_id"]
            and "program_summary" in body
            and "today_planned" in body["program_summary"]
            and "warnings" in body
        )
        check(
            "7. /students/{id} kendi",
            ok,
            f"status={r.status_code} keys={list(body.keys())}",
        )

        # ===== 8. /students/{id} başkasının öğrencisi → 404 =====
        r = client.get(f"/api/v2/teacher/students/{seed['other_student_id']}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "student_not_found"
        )
        check(
            "8. /students/{id} başkasının → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 9. /students/{id} olmayan id → 404 =====
        r = client.get("/api/v2/teacher/students/99999999")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "student_not_found"
        )
        check(
            "9. /students/{id} olmayan → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 10. /badges polling =====
        r = client.get("/api/v2/teacher/badges")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and "pending_request_count" in body
            and "at_risk_count" in body
            and "checked_at" in body
            and body["pending_request_count"] >= 1
        )
        check(
            "10. /badges polling",
            ok,
            f"status={r.status_code} pending={body.get('pending_request_count')} at_risk={body.get('at_risk_count')}",
        )

        # ===== 11. /me kestirme =====
        r = client.get("/api/v2/teacher/me")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("id") == seed["teacher_id"]
            and body.get("student_count", 0) >= 2
            and body.get("active_student_count", 0) >= 2
        )
        check(
            "11. /teacher/me",
            ok,
            f"status={r.status_code} student_count={body.get('student_count')}",
        )

        # ===== 12. Öğrenci olarak /dashboard → 403 =====
        client.post("/api/v2/auth/logout")
        _login_v2(client, STUDENT_A_EMAIL)
        r = client.get("/api/v2/teacher/dashboard")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 403
            and body.get("detail", {}).get("code") == "role_required"
        )
        check(
            "12. öğrenci /dashboard → 403",
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
