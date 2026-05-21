"""API v2 /auth P2 — Şifre sıfırlama (forgot password) smoke (Dalga 7 P2).

Senaryolar:
   1. forgot-password var olan e-posta → 200 generic + token üretildi (DB)
   2. forgot-password olmayan e-posta → 200 generic (enumeration koruması, token YOK)
   3. forgot-password tekrar → eski token geçersiz, yeni token aktif
   4. reset-password geçersiz token → 400 invalid_token
   5. reset-password password_mismatch → 422
   6. reset-password password_weak → 422
   7. reset-password password_breached → 422 (bilinen sızdırılmış şifre)
   8. reset-password happy → 200 + şifre değişti + token consumed
   9. reset-password aynı token tekrar → 400 (tek kullanımlık)
  10. reset sonrası yeni şifreyle login → 200; eski şifre → 401
  11. pasif kullanıcı forgot → token üretilmez
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import PasswordResetToken, SuspiciousIp, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2authp2_{secrets.token_hex(3)}"
EMAIL = f"{PFX}@test.invalid"
INACTIVE_EMAIL = f"{PFX}_inactive@test.invalid"
PASSWORD = "TestPass123!@xyz"
NEW_PASSWORD = "FreshPass789!@qrs"

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
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        u = User(
            email=EMAIL, password_hash=hash_password(PASSWORD), full_name=f"{PFX} User",
            role=UserRole.TEACHER, is_active=True, plan="solo_free",
            password_changed_at=now, must_change_password=False,
        )
        inactive = User(
            email=INACTIVE_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"{PFX} Inactive", role=UserRole.TEACHER, is_active=False,
            plan="solo_free", password_changed_at=now, must_change_password=False,
        )
        db.add_all([u, inactive])
        db.commit()
        return {"uid": u.id, "inactive_id": inactive.id}


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["uid"], seed["inactive_id"]]
        db.execute(sa_delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _latest_token(user_id: int) -> PasswordResetToken | None:
    with SessionLocal() as db:
        return (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user_id)
            .order_by(PasswordResetToken.id.desc())
            .first()
        )


def main() -> int:
    print(f"\n=== API v2 /auth P2 (forgot password) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded uid={seed['uid']}\n")

    try:
        c = TestClient(app)

        # 1. forgot var olan → 200 + token
        r = c.post("/api/v2/auth/forgot-password", json={"email": EMAIL})
        tok = _latest_token(seed["uid"])
        check("1. forgot var olan → 200 + token üretildi",
              r.status_code == 200 and tok is not None, f"status={r.status_code} tok={tok is not None}")
        first_token_str = tok.token if tok else None

        # 2. forgot olmayan → 200 generic, token yok
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/forgot-password", json={"email": "nobody-" + EMAIL})
        check("2. forgot olmayan → 200 generic", r.status_code == 200, f"status={r.status_code}")

        # 3. forgot tekrar → eski token geçersiz, yeni aktif
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/forgot-password", json={"email": EMAIL})
        with SessionLocal() as db:
            old = db.query(PasswordResetToken).filter(PasswordResetToken.token == first_token_str).first()
            new_tok = (
                db.query(PasswordResetToken)
                .filter(PasswordResetToken.user_id == seed["uid"], PasswordResetToken.consumed_at.is_(None))
                .order_by(PasswordResetToken.id.desc()).first()
            )
            ok = old is not None and old.consumed_at is not None and new_tok is not None and new_tok.token != first_token_str
        check("3. forgot tekrar → eski iptal + yeni aktif", ok, "")
        active_token = new_tok.token if new_tok else None

        # 4. reset geçersiz token → 400
        r = c.post("/api/v2/auth/reset-password", json={
            "token": "gecersiz_token_xyz", "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD})
        check("4. reset geçersiz token → 400", r.status_code == 400 and r.json().get("detail", {}).get("code") == "invalid_token",
              f"status={r.status_code}")

        # 5. password_mismatch → 422
        r = c.post("/api/v2/auth/reset-password", json={
            "token": active_token, "new_password": NEW_PASSWORD, "confirm_password": "BASKA123!@x"})
        check("5. password_mismatch → 422", r.status_code == 422 and r.json().get("detail", {}).get("code") == "password_mismatch",
              f"status={r.status_code}")

        # 6. password_weak → 422
        r = c.post("/api/v2/auth/reset-password", json={
            "token": active_token, "new_password": "kisa", "confirm_password": "kisa"})
        check("6. password_weak → 422", r.status_code == 422 and r.json().get("detail", {}).get("code") == "password_weak",
              f"status={r.status_code}")

        # 7. password_breached → 422 (Password123! gibi bilinen sızıntı? test için yaygın)
        r = c.post("/api/v2/auth/reset-password", json={
            "token": active_token, "new_password": "Password1", "confirm_password": "Password1"})
        # Password1 yaygın liste veya breach'te; weak veya breached olabilir
        code7 = r.json().get("detail", {}).get("code")
        check("7. zayıf/sızdırılmış şifre reddi → 422", r.status_code == 422 and code7 in ("password_weak", "password_breached"),
              f"status={r.status_code} code={code7}")

        # 8. reset happy → 200 + consumed
        r = c.post("/api/v2/auth/reset-password", json={
            "token": active_token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD})
        ok = r.status_code == 200
        with SessionLocal() as db:
            row = db.query(PasswordResetToken).filter(PasswordResetToken.token == active_token).first()
            consumed = row is not None and row.consumed_at is not None
        check("8. reset happy → 200 + token consumed", ok and consumed, f"status={r.status_code} consumed={consumed}")

        # 9. aynı token tekrar → 400
        r = c.post("/api/v2/auth/reset-password", json={
            "token": active_token, "new_password": "AnotherPass1!@z", "confirm_password": "AnotherPass1!@z"})
        check("9. aynı token tekrar → 400 (tek kullanım)", r.status_code == 400, f"status={r.status_code}")

        # 10. yeni şifreyle login → 200; eski şifre → 401
        get_login_limiter().reset()
        r = TestClient(app).post("/api/v2/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD})
        new_ok = r.status_code == 200
        get_login_limiter().reset()
        r = TestClient(app).post("/api/v2/auth/login", json={"email": EMAIL, "password": PASSWORD})
        old_rejected = r.status_code == 401
        check("10. yeni şifre login 200 + eski 401", new_ok and old_rejected, f"new={new_ok} old_rejected={old_rejected}")

        # 11. pasif kullanıcı forgot → token üretilmez
        get_login_limiter().reset()
        c.post("/api/v2/auth/forgot-password", json={"email": INACTIVE_EMAIL})
        inactive_tok = _latest_token(seed["inactive_id"])
        check("11. pasif forgot → token üretilmez", inactive_tok is None, f"tok={inactive_tok is not None}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
