"""API v2 öğretmen 5d.2 smoke — warnings-feed + reset-password + password-change.

Senaryolar (10):
   1. GET /dashboard/warnings-feed — happy
   2. POST /students/{id}/reset-password happy → temp_password döner
   3. POST /students/{id}/reset-password başkasının → 404
   4. POST /me/password-change boş confirm → 422 password_mismatch
   5. POST /me/password-change zayıf şifre → 422 password_weak
   6. POST /me/password-change yanlış mevcut → 422 wrong_current_password
   7. POST /me/password-change aynı şifre → 422 password_same
   8. POST /me/password-change happy → 200 + must_change_password=False
   9. Eski şifre artık çalışmıyor → login 401
  10. Yeni şifre çalışıyor → login 200
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2_5d2_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_s2@test.invalid"
PASSWORD = "TestPass123!@xyz"
NEW_PASSWORD = "BrandNewSecure!9zXq"

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
            full_name="V2 5d2 Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer 5d2", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
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
        db.add_all([student, other_student])
        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(User).where(User.id.in_([
            seed["teacher_id"], seed["other_teacher_id"],
            seed["student_id"], seed["other_student_id"],
        ])))
        db.commit()


def _login(client: TestClient, email: str, password: str = PASSWORD) -> int:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": password})
    return r.status_code


def main() -> int:
    print(f"\n=== API v2 /teacher 5d.2 (warnings/reset-password/password-change) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        client = TestClient(app)
        assert _login(client, TEACHER_EMAIL) == 200

        # 1) Warnings feed
        r = client.get("/api/v2/teacher/dashboard/warnings-feed")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and isinstance(body.get("rows"), list)
            and "total" in body
        )
        check("1. GET /dashboard/warnings-feed happy",
              ok, f"status={r.status_code}")

        # 2) Reset password happy
        r = client.post(f"/api/v2/teacher/students/{seed['student_id']}/reset-password")
        body = r.json() if r.text else {}
        new_temp_pw = body.get("data", {}).get("temp_password")
        ok = (
            r.status_code == 200
            and isinstance(new_temp_pw, str)
            and len(new_temp_pw) >= 8
            and body.get("data", {}).get("email") == STUDENT_EMAIL
        )
        check("2. POST /reset-password happy", ok, f"status={r.status_code} pw_len={len(new_temp_pw or '')}")

        # 3) Reset password başkasının
        r = client.post(f"/api/v2/teacher/students/{seed['other_student_id']}/reset-password")
        ok = r.status_code == 404
        check("3. POST /reset-password başkasının → 404", ok, f"status={r.status_code}")

        # ============ PASSWORD CHANGE ============
        # 4) Mismatch
        r = client.post(
            "/api/v2/me/password-change",
            json={
                "current_password": PASSWORD,
                "new_password": NEW_PASSWORD,
                "confirm_password": "different",
            },
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "password_mismatch"
        )
        check("4. password-change mismatch → 422", ok, f"status={r.status_code}")

        # 5) Weak
        r = client.post(
            "/api/v2/me/password-change",
            json={
                "current_password": PASSWORD,
                "new_password": "123",
                "confirm_password": "123",
            },
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "password_weak"
        )
        check("5. password-change weak → 422", ok, f"status={r.status_code}")

        # 6) Wrong current
        r = client.post(
            "/api/v2/me/password-change",
            json={
                "current_password": "WrongOne123!",
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "wrong_current_password"
        )
        check("6. password-change wrong current → 422", ok, f"status={r.status_code}")

        # 7) Same as current
        r = client.post(
            "/api/v2/me/password-change",
            json={
                "current_password": PASSWORD,
                "new_password": PASSWORD,
                "confirm_password": PASSWORD,
            },
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "password_same"
        )
        check("7. password-change same → 422", ok, f"status={r.status_code}")

        # 8) Happy
        r = client.post(
            "/api/v2/me/password-change",
            json={
                "current_password": PASSWORD,
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("must_change_password") is False
        )
        check("8. password-change happy", ok, f"status={r.status_code} body={body}")

        # 9) Old password no longer works
        get_login_limiter().reset()
        client_old = TestClient(app)
        old_status = _login(client_old, TEACHER_EMAIL, PASSWORD)
        ok = old_status == 401
        check("9. Eski şifre artık çalışmıyor → 401", ok, f"status={old_status}")

        # 10) New password works
        get_login_limiter().reset()
        client_new = TestClient(app)
        new_status = _login(client_new, TEACHER_EMAIL, NEW_PASSWORD)
        ok = new_status == 200
        check("10. Yeni şifre çalışıyor → 200", ok, f"status={new_status}")

    finally:
        _cleanup(seed)
        print(f"\n  cleanup OK\n")

    print(f"\n=== SONUÇ: {passed}/{passed + len(failed)} PASS ===")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
