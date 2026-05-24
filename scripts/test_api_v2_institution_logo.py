"""API v2 — kurum logosu (co-branding) smoke.

Senaryolar:
   1.  Non-super-admin upload → 403
   2.  Anonim serve → 401
   3.  Süper admin geçersiz tür yükler → 400 invalid_file_type
   4.  Süper admin >2MB yükler → 400 file_too_large
   5.  Süper admin PNG yükler → 200 + has_logo True
   6.  /me (kurum yöneticisi) → institution.has_logo + logo_url
   7.  Kurum yöneticisi logoyu serve eder → 200 + içerik birebir
   8.  Bağlı öğretmen serve eder → 200
   9.  Cross-tenant yönetici serve → 404
   10. Admin kurum detayı → has_logo + logo_url
   11. Süper admin logoyu kaldırır → 200 + has_logo False
   12. Kaldırınca serve → 404
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
from app.models import AuditLog, Institution, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"logo{secrets.token_hex(3)}"
PASSWORD = "LogoPass1!@xyz"
SA = f"{PFX}_sa@test.invalid"
ADMIN = f"{PFX}_adm@test.invalid"
TEACHER = f"{PFX}_tch@test.invalid"
B_ADMIN = f"{PFX}_badm@test.invalid"

PNG = b"\x89PNG\r\n\x1a\n" + b"FAKE-LOGO-BYTES-" * 4

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
        a = Institution(name=f"{PFX} A", slug=f"{PFX}-a", contact_email=f"{PFX}a@t.invalid",
                        plan="etut_standart", is_active=True)
        b = Institution(name=f"{PFX} B", slug=f"{PFX}-b", contact_email=f"{PFX}b@t.invalid",
                        plan="etut_standart", is_active=True)
        db.add_all([a, b]); db.flush()

        def mk(email, role, inst):
            return User(email=email, password_hash=pwd, full_name=email, role=role,
                        institution_id=inst, is_active=True, password_changed_at=now,
                        must_change_password=False, email_verified_at=now)

        sa = User(email=SA, password_hash=pwd, full_name="SA", role=UserRole.SUPER_ADMIN,
                  institution_id=None, is_active=True, password_changed_at=now,
                  must_change_password=False, email_verified_at=now)
        adm = mk(ADMIN, UserRole.INSTITUTION_ADMIN, a.id)
        tch = mk(TEACHER, UserRole.TEACHER, a.id)
        badm = mk(B_ADMIN, UserRole.INSTITUTION_ADMIN, b.id)
        db.add_all([sa, adm, tch, badm]); db.flush()
        out = {"a_id": a.id, "b_id": b.id,
               "uids": [sa.id, adm.id, tch.id, badm.id]}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(seed["uids"])))
        db.execute(sa_delete(User).where(User.id.in_(seed["uids"])))
        db.execute(sa_delete(Institution).where(Institution.id.in_([seed["a_id"], seed["b_id"]])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.commit()


def _login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login {email} {r.status_code} {r.text[:120]}")
    return c


def main() -> int:
    print(f"\n=== Kurum logosu (co-branding) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    aid = seed["a_id"]
    try:
        sa = _login(SA)
        adm = _login(ADMIN)
        tch = _login(TEACHER)
        badm = _login(B_ADMIN)

        # 1. non-super-admin upload → 403
        r = adm.post(f"/api/v2/admin/institutions/{aid}/logo",
                     files={"file": ("l.png", PNG, "image/png")})
        check("1. Kurum yöneticisi upload → 403", r.status_code == 403, f"{r.status_code}")

        # 2. anonim serve → 401
        r = TestClient(app).get(f"/api/v2/institution/logo/{aid}")
        check("2. Anonim serve → 401", r.status_code == 401, f"{r.status_code}")

        # 3. geçersiz tür → 400
        r = sa.post(f"/api/v2/admin/institutions/{aid}/logo",
                    files={"file": ("l.txt", b"hello", "text/plain")})
        check("3. Geçersiz tür → 400 invalid_file_type",
              r.status_code == 400 and r.json()["detail"]["code"] == "invalid_file_type", f"{r.status_code} {r.text[:100]}")

        # 4. >2MB → 400
        big = b"x" * (2 * 1024 * 1024 + 10)
        r = sa.post(f"/api/v2/admin/institutions/{aid}/logo",
                    files={"file": ("big.png", big, "image/png")})
        check("4. >2MB → 400 file_too_large",
              r.status_code == 400 and r.json()["detail"]["code"] == "file_too_large", f"{r.status_code}")

        # 5. PNG yükle → 200 + has_logo
        r = sa.post(f"/api/v2/admin/institutions/{aid}/logo",
                    files={"file": ("logo.png", PNG, "image/png")})
        ok = r.status_code == 200 and r.json()["data"]["institution"]["has_logo"] is True
        check("5. Süper admin PNG yükler → 200 + has_logo", ok, f"{r.status_code} {r.text[:140]}")

        # 6. /me kurum yöneticisi → has_logo + logo_url
        r = adm.get("/api/v2/me")
        inst = r.json().get("institution") or {}
        check("6. /me institution.has_logo + logo_url",
              inst.get("has_logo") is True and inst.get("logo_url") == f"/api/v2/institution/logo/{aid}",
              f"{inst}")

        # 7. kurum yöneticisi serve → 200 + içerik
        r = adm.get(f"/api/v2/institution/logo/{aid}")
        check("7. Kurum yöneticisi serve → 200 + içerik birebir",
              r.status_code == 200 and r.content == PNG, f"{r.status_code} len={len(r.content)}")

        # 8. bağlı öğretmen serve → 200
        r = tch.get(f"/api/v2/institution/logo/{aid}")
        check("8. Bağlı öğretmen serve → 200", r.status_code == 200, f"{r.status_code}")

        # 9. cross-tenant yönetici serve → 404
        r = badm.get(f"/api/v2/institution/logo/{aid}")
        check("9. Cross-tenant serve → 404", r.status_code == 404, f"{r.status_code}")

        # 10. admin detay → has_logo + logo_url
        r = sa.get(f"/api/v2/admin/institutions/{aid}")
        ib = r.json()["institution"]
        check("10. Admin detay has_logo + logo_url",
              ib.get("has_logo") is True and ib.get("logo_url") == f"/api/v2/institution/logo/{aid}", f"{ib}")

        # 11. logo kaldır → 200 + has_logo False
        r = sa.post(f"/api/v2/admin/institutions/{aid}/logo/delete")
        check("11. Logo kaldır → 200 + has_logo False",
              r.status_code == 200 and r.json()["data"]["institution"]["has_logo"] is False, f"{r.status_code} {r.text[:120]}")

        # 12. kaldırınca serve → 404
        r = adm.get(f"/api/v2/institution/logo/{aid}")
        check("12. Kaldırınca serve → 404", r.status_code == 404, f"{r.status_code}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
