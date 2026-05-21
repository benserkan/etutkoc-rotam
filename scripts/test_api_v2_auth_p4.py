"""API v2 2FA/TOTP smoke (Dalga 7 P4).

Senaryolar:
   1. 2fa/status — teacher (rol uygun değil) → available=False
   2. 2fa/setup — teacher → 403 two_factor_not_available
   3. 2fa/status — institution_admin → available=True, enabled=False
   4. 2fa/setup — admin → secret + provisioning_uri + 10 backup code
   5. 2fa/enable — yanlış kod → 422
   6. 2fa/enable — doğru TOTP kod → 200 enabled
   7. 2fa/status — enabled=True + remaining_backup_codes=10
   8. login (2fa aktif) → two_factor_required=True + challenge, cookie YOK
   9. 2fa/verify — yanlış kod → 401 invalid_2fa_code
  10. 2fa/verify — doğru TOTP → 200 + cookie + user
  11. 2fa/verify — yedek kod ile → 200 (tek kullanım, remaining azalır)
  12. 2fa/disable — doğru kod → 200, enabled False; sonraki login 2fa istemez
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timezone

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import ActiveSession, AuditLog, SuspiciousIp, TotpBackupCode, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2authp4_{_secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "AdminPass1!@xyz"
ACCESS = settings.auth_cookie_access_name

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
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        admin = User(
            email=ADMIN_EMAIL, password_hash=pwd, full_name=f"{PFX} Admin",
            role=UserRole.INSTITUTION_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
            email_verified_at=now,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, is_active=True,
            password_changed_at=now, must_change_password=False,
            email_verified_at=now,
        )
        db.add_all([admin, teacher])
        db.commit()
        return {"admin_id": admin.id, "teacher_id": teacher.id}


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["admin_id"], seed["teacher_id"]]
        db.execute(sa_delete(TotpBackupCode).where(TotpBackupCode.user_id.in_(uids)))
        db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(uids)))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login_client(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def _admin_secret() -> str | None:
    with SessionLocal() as db:
        u = db.get(User, _SEED["admin_id"])
        return u.totp_secret if u else None


def main() -> int:
    global _SEED
    print(f"\n=== API v2 2FA/TOTP (P4) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    _SEED = _seed()
    print(f"  seeded admin={_SEED['admin_id']} teacher={_SEED['teacher_id']}\n")

    try:
        # 1. teacher status → available False
        tc = _login_client(TEACHER_EMAIL)
        r = tc.get("/api/v2/me/2fa/status")
        check("1. teacher status available=False", r.status_code == 200 and r.json().get("available") is False,
              f"status={r.status_code} {r.text[:100]}")

        # 2. teacher setup → 403
        r = tc.post("/api/v2/me/2fa/setup")
        check("2. teacher setup → 403", r.status_code == 403 and r.json().get("detail", {}).get("code") == "two_factor_not_available",
              f"status={r.status_code}")

        # 3. admin status → available True, enabled False
        ac = _login_client(ADMIN_EMAIL)
        r = ac.get("/api/v2/me/2fa/status")
        j = r.json()
        check("3. admin status available=True enabled=False", r.status_code == 200 and j.get("available") and not j.get("enabled"),
              f"status={r.status_code} {j}")

        # 4. admin setup → secret + uri + 10 backup
        r = ac.post("/api/v2/me/2fa/setup")
        j = r.json()
        secret = j.get("secret")
        backup_codes = j.get("backup_codes", [])
        ok = r.status_code == 200 and secret and "otpauth://" in (j.get("provisioning_uri") or "") and len(backup_codes) == 10
        check("4. admin setup → secret+uri+10 backup", ok, f"status={r.status_code} backups={len(backup_codes)}")

        # 5. enable yanlış kod → 422
        r = ac.post("/api/v2/me/2fa/enable", json={"code": "000000"})
        check("5. enable yanlış kod → 422", r.status_code == 422, f"status={r.status_code}")

        # 6. enable doğru kod → 200
        good = pyotp.TOTP(secret).now()
        r = ac.post("/api/v2/me/2fa/enable", json={"code": good})
        check("6. enable doğru kod → 200 enabled", r.status_code == 200 and r.json()["data"]["enabled"] is True,
              f"status={r.status_code} {r.text[:120]}")

        # 7. status enabled + 10 backup
        r = ac.get("/api/v2/me/2fa/status")
        j = r.json()
        check("7. status enabled + 10 backup", j.get("enabled") and j.get("remaining_backup_codes") == 10, f"{j}")

        # 8. login (2fa aktif) → two_factor_required + challenge, cookie yok
        get_login_limiter().reset()
        lc = TestClient(app)
        r = lc.post("/api/v2/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
        j = r.json()
        cookie_set = any(ck.name == ACCESS for ck in lc.cookies.jar)
        challenge = j.get("challenge")
        ok = r.status_code == 200 and j.get("two_factor_required") is True and challenge and not cookie_set
        check("8. login → two_factor_required + challenge (cookie yok)", ok,
              f"status={r.status_code} 2fa={j.get('two_factor_required')} cookie={cookie_set}")

        # 9. 2fa/verify yanlış kod → 401
        get_login_limiter().reset()
        r = lc.post("/api/v2/auth/2fa/verify", json={"challenge": challenge, "code": "000000"})
        check("9. 2fa/verify yanlış → 401 invalid_2fa_code",
              r.status_code == 401 and r.json().get("detail", {}).get("code") == "invalid_2fa_code", f"status={r.status_code}")

        # 10. 2fa/verify doğru TOTP → 200 + cookie
        get_login_limiter().reset()
        good = pyotp.TOTP(secret).now()
        r = lc.post("/api/v2/auth/2fa/verify", json={"challenge": challenge, "code": good})
        cookie_set = any(ck.name == ACCESS for ck in lc.cookies.jar)
        ok = r.status_code == 200 and r.json().get("user", {}).get("email") == ADMIN_EMAIL and cookie_set
        check("10. 2fa/verify doğru TOTP → 200 + cookie", ok, f"status={r.status_code} cookie={cookie_set} {r.text[:100]}")

        # 11. yedek kod ile verify (yeni challenge al)
        get_login_limiter().reset()
        lc2 = TestClient(app)
        r = lc2.post("/api/v2/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
        ch2 = r.json().get("challenge")
        get_login_limiter().reset()
        r = lc2.post("/api/v2/auth/2fa/verify", json={"challenge": ch2, "code": backup_codes[0]})
        ok = r.status_code == 200 and any(ck.name == ACCESS for ck in lc2.cookies.jar)
        check("11. yedek kod ile verify → 200", ok, f"status={r.status_code} {r.text[:100]}")
        r = ac.get("/api/v2/me/2fa/status")
        check("11b. yedek kod tüketildi (9 kaldı)", r.json().get("remaining_backup_codes") == 9, f"{r.json()}")

        # 12. disable doğru kod → enabled False; sonraki login 2fa istemez
        good = pyotp.TOTP(secret).now()
        r = ac.post("/api/v2/me/2fa/disable", json={"code": good})
        check("12. disable → 200 enabled False", r.status_code == 200 and r.json()["data"]["enabled"] is False, f"status={r.status_code}")
        get_login_limiter().reset()
        lc3 = TestClient(app)
        r = lc3.post("/api/v2/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
        j = r.json()
        check("12b. disable sonrası login 2fa istemez", r.status_code == 200 and not j.get("two_factor_required") and j.get("user"),
              f"status={r.status_code} 2fa={j.get('two_factor_required')}")

    finally:
        _cleanup(_SEED)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


_SEED: dict = {}

if __name__ == "__main__":
    raise SystemExit(main())
