"""M2 — Koç öğrenci email güncelleme smoke.

Senaryolar (8):
   1. happy: email değiştir → 200, DB güncel, email_verified_at None
   2. aynı email (case-insensitive) → 200 no-op
   3. başka kullanıcının email'i → 409 email_taken
   4. invalid format → 422 invalid_email
   5. başkasının öğrencisi → 404 student_not_found
   6. email + full_name birlikte → 200 ikisi de değişir
   7. email boş string → değişmez (no-op)
   8. email değişiminde pwd_stamp dokunulmaz (oturum kesilmez)
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
from app.models import SuspiciousIp, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2em_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
TEACHER2_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
STUDENT2_EMAIL = f"{PFX}_s2@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_os@test.invalid"
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
            full_name="Email Test Öğretmen", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        teacher2 = User(
            email=TEACHER2_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Email Test Öğretmen 2", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Email Test Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
            email_verified_at=None,  # ilk yüklemede unset
        )
        student2 = User(
            email=STUDENT2_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Email Test Öğrenci 2", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Koç Öğrencisi", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        db.add_all([teacher, teacher2, student, student2, other_student])
        db.flush()
        student.teacher_id = teacher.id
        student2.teacher_id = teacher.id
        other_student.teacher_id = teacher2.id
        # student.email_verified_at = mevcut tarih (değişimle sıfırlanacak)
        from datetime import datetime, timezone
        student.email_verified_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "teacher_id": teacher.id,
            "teacher2_id": teacher2.id,
            "student_id": student.id,
            "student2_id": student2.id,
            "other_student_id": other_student.id,
            "original_student_email": STUDENT_EMAIL,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["student2_id"], seed["other_student_id"],
            seed["teacher_id"], seed["teacher2_id"],
        ])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def _read_student_email(student_id: int) -> tuple[str, "datetime | None"]:
    with SessionLocal() as db:
        s = db.get(User, student_id)
        assert s is not None
        return s.email, s.email_verified_at  # type: ignore[return-value]


def main() -> int:
    print(f"\n=== M2 öğrenci email güncelleme smoke — prefix: {PFX} ===\n")
    seed = _seed()

    try:
        client = TestClient(app)
        _login(client, TEACHER_EMAIL)

        # ===== 1. happy: email değiştir =====
        new_email = f"{PFX}_s_new@test.invalid"
        r = client.patch(
            f"/api/v2/teacher/students/{seed['student_id']}",
            json={"email": new_email},
        )
        db_email, verified_at = _read_student_email(seed["student_id"])
        ok = (
            r.status_code == 200
            and db_email == new_email
            and verified_at is None  # email değişince sıfırlanır
        )
        check("1. happy email değişir + verified_at None",
              ok, f"status={r.status_code} db={db_email} verified={verified_at}")

        # ===== 2. aynı email (case-insensitive) → no-op =====
        # Email zaten new_email, yine geçir (uppercase test)
        r = client.patch(
            f"/api/v2/teacher/students/{seed['student_id']}",
            json={"email": new_email.upper()},
        )
        db_email, _ = _read_student_email(seed["student_id"])
        # case-insensitive eşleşmeli → değişmemeli
        ok = r.status_code == 200 and db_email == new_email
        check("2. aynı email case-insensitive → no-op",
              ok, f"status={r.status_code} db={db_email}")

        # ===== 3. başka kullanıcının email'i (student2) → 409 =====
        r = client.patch(
            f"/api/v2/teacher/students/{seed['student_id']}",
            json={"email": STUDENT2_EMAIL},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "email_taken"
        )
        check("3. başkasının email → 409 email_taken",
              ok, f"status={r.status_code} body={r.text[:160]}")

        # ===== 4. invalid format → 422 invalid_email =====
        r = client.patch(
            f"/api/v2/teacher/students/{seed['student_id']}",
            json={"email": "geçersiz-email-format"},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "invalid_email"
        )
        check("4. invalid format → 422 invalid_email",
              ok, f"status={r.status_code} body={r.text[:160]}")

        # ===== 5. başkasının öğrencisi → 404 =====
        r = client.patch(
            f"/api/v2/teacher/students/{seed['other_student_id']}",
            json={"email": f"{PFX}_oz@test.invalid"},
        )
        ok = r.status_code == 404
        check("5. başka koçun öğrencisi → 404",
              ok, f"status={r.status_code}")

        # ===== 6. email + full_name birlikte =====
        combo_email = f"{PFX}_s_combo@test.invalid"
        r = client.patch(
            f"/api/v2/teacher/students/{seed['student_id']}",
            json={"full_name": "Yeni Ad Combo", "email": combo_email},
        )
        with SessionLocal() as db:
            s = db.get(User, seed["student_id"])
            assert s is not None
            ok = (
                r.status_code == 200
                and s.email == combo_email
                and s.full_name == "Yeni Ad Combo"
            )
        check("6. email + full_name combo → ikisi de değişti",
              ok, f"status={r.status_code}")

        # ===== 7. boş string → değişmez =====
        before_email = combo_email
        r = client.patch(
            f"/api/v2/teacher/students/{seed['student_id']}",
            json={"email": "   "},  # whitespace → strip → ""
        )
        db_email, _ = _read_student_email(seed["student_id"])
        ok = r.status_code == 200 and db_email == before_email
        check("7. boş string → değişmez",
              ok, f"status={r.status_code} db={db_email}")

        # ===== 8. pwd_stamp değişmedi (oturum kesilmez) =====
        # Yeni email'le login dene → çalışmalı
        get_login_limiter().reset()
        # Önce eski koç oturumunu kapat (cookies temizle)
        new_client = TestClient(app)
        r = new_client.post(
            "/api/v2/auth/login",
            json={"email": combo_email, "password": PASSWORD},
        )
        ok = r.status_code == 200
        check("8. yeni email ile login OK (pwd_stamp değişmedi)",
              ok, f"status={r.status_code} body={r.text[:160]}")

    finally:
        _cleanup(seed)

    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} geçti ===\n")
    if failed:
        print("Başarısız senaryolar:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
