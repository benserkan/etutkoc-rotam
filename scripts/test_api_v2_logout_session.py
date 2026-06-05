"""Logout, Jinja session cookie'sini de temizler mi? — güvenlik regresyonu.

BUG (2026-06-05): süper admin impersonate yapıp döndükten sonra
`/admin/impersonate/end` admin'in user_id'sini Jinja `session` cookie'sine yazıyor.
`v2_logout` yalnız BFF cookie'lerini siliyordu → BFF dependency'nin 3. fallback
kanalı (`session.get("user_id")`) ile admin logout sonrası HÂLÂ authenticate
oluyordu → /admin açık kalıyordu. Düzeltme: logout `request.session.clear()` de yapar.

Bu test bug'ı birebir üretir:
  impersonate → end (session=admin) → /me=admin (sanity) → logout → /me MUST 401.
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

PFX = f"logout_{_secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PWD = "Logout!2345"

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
    print(f"\n=== logout session-clear smoke — {PFX} ===\n")
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
        # ===== Senaryo A: impersonation sonrası logout =====
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": SUPER_EMAIL, "password": PWD})
        check("A0. süper admin login", r.status_code == 200, f"{r.status_code} {r.text[:120]}")

        r = c.post(f"/api/v2/admin/users/{teacher_id}/impersonate",
                   json={"reason": "Logout session temizleme testi"})
        check("A1. impersonate → 200", r.status_code == 200, f"{r.status_code} {r.text[:140]}")

        r = c.post("/api/v2/admin/impersonate/end")
        check("A2. impersonate end → 200", r.status_code == 200, f"{r.status_code} {r.text[:140]}")

        # session cookie artık admin'i taşıyor (impersonate/end yazdı)
        has_session = any(ck == "session" for ck in c.cookies.keys())
        check("A3. end sonrası Jinja session cookie var", has_session, f"cookies={list(c.cookies.keys())}")

        r = c.get("/api/v2/auth/me")
        check("A4. logout ÖNCESİ /me = süper admin (sanity)",
              r.status_code == 200 and r.json().get("id") == super_id,
              f"{r.status_code} id={r.json().get('id')}")

        # >>> ÇIKIŞ <<<
        r = c.post("/api/v2/auth/logout")
        check("A5. logout → 200", r.status_code == 200, f"{r.status_code}")

        # KRİTİK: logout sonrası HİÇBİR kanaldan authenticate OLMAMALI
        r = c.get("/api/v2/auth/me")
        check("A6. logout SONRASI /me = 401 (session de temizlendi)",
              r.status_code == 401,
              f"BEKLENEN 401, GELEN {r.status_code} id={(r.json() or {}).get('id') if r.status_code == 200 else '-'}")

        r = c.get("/api/v2/admin/dashboard")
        check("A7. logout sonrası /admin/dashboard = 401 (panel kapalı)",
              r.status_code == 401, f"BEKLENEN 401, GELEN {r.status_code}")

        # session cookie tarayıcı jar'ından da düşmüş olmalı
        still_session = any(ck == "session" for ck in c.cookies.keys())
        check("A8. logout sonrası session cookie silindi", not still_session,
              f"cookies={list(c.cookies.keys())}")

        # ===== Senaryo B: normal (impersonation'sız) logout regresyonu =====
        c2 = TestClient(app)
        get_login_limiter().reset()
        r = c2.post("/api/v2/auth/login", json={"email": SUPER_EMAIL, "password": PWD})
        check("B0. yeniden login", r.status_code == 200, f"{r.status_code}")
        r = c2.get("/api/v2/auth/me")
        check("B1. /me = admin", r.status_code == 200 and r.json().get("id") == super_id, f"{r.status_code}")
        r = c2.post("/api/v2/auth/logout")
        r = c2.get("/api/v2/auth/me")
        check("B2. normal logout sonrası /me = 401", r.status_code == 401, f"{r.status_code}")

    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_([super_id, teacher_id])))
            db.execute(sa_delete(User).where(User.id.in_([super_id, teacher_id])))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
