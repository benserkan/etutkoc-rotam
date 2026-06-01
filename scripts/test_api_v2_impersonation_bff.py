"""BFF-JWT impersonation uçtan uca smoke (2026-06-01).

Süper admin impersonate edince BFF cookie HEDEFe geçer (imp_by claim); Next.js
panelleri hedefi görür. /auth/me hedefi döner, /auth/impersonation-status active.
Refresh imp_by'ı korur. end → admin cookie geri basılır, /auth/me admin'i döner.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import SuspiciousIp, User, UserRole
from app.models.active_session import ActiveSession
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"impbff_{_secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PWD = "ImpBff!2345"

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


def main() -> int:
    print(f"\n=== BFF impersonation smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        sup = User(email=SUPER_EMAIL, password_hash=hash_password(PWD),
                   full_name=f"{PFX} Super", role=UserRole.SUPER_ADMIN, is_active=True,
                   password_changed_at=now, must_change_password=False)
        tch = User(email=TEACHER_EMAIL, password_hash=hash_password(PWD),
                   full_name=f"{PFX} Teacher", role=UserRole.TEACHER, is_active=True,
                   password_changed_at=now, must_change_password=False)
        db.add_all([sup, tch])
        db.commit()
        super_id, teacher_id = sup.id, tch.id

    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": SUPER_EMAIL, "password": PWD})
        check("0. süper admin login", r.status_code == 200, f"{r.status_code} {r.text[:120]}")

        # 1. impersonate happy → cookie hedefe geçer
        r = c.post(f"/api/v2/admin/users/{teacher_id}/impersonate",
                   json={"reason": "Uçtan uca impersonation testi"})
        check("1. impersonate → 200 + redirect /teacher",
              r.status_code == 200 and r.json().get("redirect_url") == "/teacher",
              f"{r.status_code} {r.text[:160]}")

        # 2. /auth/me artık HEDEFi döner (cookie swap)
        r = c.get("/api/v2/auth/me")
        check("2. /auth/me = hedef öğretmen (cookie swap)",
              r.status_code == 200 and r.json().get("id") == teacher_id,
              f"{r.status_code} id={r.json().get('id')} (teacher={teacher_id})")

        # 3. impersonation-status active + isimler
        r = c.get("/api/v2/auth/impersonation-status")
        j = r.json()
        check("3. impersonation-status active + isimler",
              r.status_code == 200 and j.get("active") is True
              and j.get("target_name") == f"{PFX} Teacher"
              and j.get("impersonator_name") == f"{PFX} Super",
              f"{r.status_code} {j}")

        # 4. refresh imp_by'ı korur → /auth/me hâlâ hedef
        r = c.post("/api/v2/auth/refresh")
        r2 = c.get("/api/v2/auth/impersonation-status")
        check("4. refresh sonrası impersonation sürer",
              r.status_code == 200 and r2.json().get("active") is True,
              f"refresh={r.status_code} status_active={r2.json().get('active')}")

        # 5. end → admin cookie geri + redirect /admin
        r = c.post("/api/v2/admin/impersonate/end")
        check("5. end → 200 + /admin",
              r.status_code == 200 and r.json().get("redirect_url") == "/admin",
              f"{r.status_code} {r.text[:160]}")

        # 6. /auth/me artık ADMIN (restore)
        r = c.get("/api/v2/auth/me")
        check("6. /auth/me = süper admin (restore)",
              r.status_code == 200 and r.json().get("id") == super_id,
              f"{r.status_code} id={r.json().get('id')} (super={super_id})")

        # 7. status artık pasif
        r = c.get("/api/v2/auth/impersonation-status")
        check("7. impersonation-status pasif",
              r.status_code == 200 and r.json().get("active") is False,
              f"{r.status_code} {r.json()}")

    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(ActiveSession).where(
                ActiveSession.user_id.in_([super_id, teacher_id])
            ))
            db.execute(sa_delete(User).where(User.id.in_([super_id, teacher_id])))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
