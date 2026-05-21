"""API v2 /admin/security-monitor/* (Oturumlar + Canlı + IP + Impersonation) smoke (D6 G3).

Senaryolar:
   1. live/feed Teacher → 403
   2. live/feed Anonim → 401
   3. live/feed happy (since_seconds + items, audit kaydı görünür)
   4. live/feed since_seconds clamp (geçersiz büyük → 400/422)
   5. revoke happy → 200 + invalidate + oturum kapanır
   6. revoke bilinmeyen token → 404
   7. revoke Teacher → 403
   8. ips/block happy → 200 + invalidate
   9. ips/block boş ip → 400
  10. ips/block hours clamp (>720 → 720 kabul, 200)
  11. ips/unblock happy → 200
  12. ips/unblock bilinmeyen ip → 404
  13. ips/block Teacher → 403
  14. impersonations/{id}/end happy → 200 + IMPERSONATE_REVOKED
  15. impersonations/{id}/end bilinmeyen → 404
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    ActiveSession,
    AuditAction,
    AuditLog,
    ImpersonationSession,
    SuspiciousIp,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adg3{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
TARGET_EMAIL = f"{PFX}_target@test.invalid"
PASSWORD = "TestPassG3!23"
TEST_IP = f"203.0.113.{secrets.randbelow(250) + 1}"

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
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        target = User(
            email=TARGET_EMAIL, password_hash=pwd, full_name=f"{PFX} Target",
            role=UserRole.STUDENT, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher, target])
        db.flush()
        db.add(AuditLog(
            actor_id=super_admin.id, action=AuditAction.LOGIN_SUCCESS,
            created_at=now, ip_address="127.0.0.1",
        ))
        sess = ActiveSession(
            session_token=f"{PFX}_tok_{secrets.token_hex(8)}",
            user_id=target.id, role="student", ip="198.51.100.5",
            user_agent="test", login_at=now, last_seen_at=now,
        )
        db.add(sess)
        imp = ImpersonationSession(
            actor_user_id=super_admin.id, target_user_id=target.id,
            reason="smoke test gerekçesi", started_at=now,
            expires_at=now + timedelta(minutes=30), ip="127.0.0.1",
        )
        db.add(imp)
        db.flush()
        out = {
            "super_id": super_admin.id, "teacher_id": teacher.id,
            "target_id": target.id, "session_token": sess.session_token,
            "imp_id": imp.id,
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["super_id"], seed["teacher_id"], seed["target_id"]]
        db.execute(sa_delete(ImpersonationSession).where(ImpersonationSession.id == seed["imp_id"]))
        db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == TEST_IP))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/security-monitor sessions/live/ips/imp (G3) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded session={seed['session_token'][:12]}… imp={seed['imp_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. live/feed Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/live/feed")
        check("1. live/feed Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get("/api/v2/admin/security-monitor/live/feed")
        check("2. live/feed Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. live/feed happy
        r = sc.get("/api/v2/admin/security-monitor/live/feed?since_seconds=3600")
        j = r.json()
        ok = (
            r.status_code == 200 and j["since_seconds"] == 3600
            and "items" in j
            and all("type" in it and "severity" in it for it in j["items"])
        )
        check("3. live/feed happy", ok, f"status={r.status_code} {r.text[:120]}")

        # 4. since_seconds clamp (geçersiz büyük → 422)
        r = sc.get("/api/v2/admin/security-monitor/live/feed?since_seconds=999999")
        check("4. since_seconds üst sınır → 422", r.status_code == 422, f"status={r.status_code}")

        # 5. revoke happy
        r = sc.post(f"/api/v2/admin/security-monitor/sessions/{seed['session_token']}/revoke")
        j = r.json()
        ok = r.status_code == 200 and "admin:security:overview" in j["invalidate"]
        check("5. revoke happy + invalidate", ok, f"status={r.status_code} {r.text[:120]}")
        # doğrula: oturum terminated
        with SessionLocal() as db:
            s = db.query(ActiveSession).filter(ActiveSession.session_token == seed["session_token"]).first()
            check("5b. oturum terminated", s is not None and s.terminated_at is not None, "")

        # 6. revoke bilinmeyen → 404
        r = sc.post("/api/v2/admin/security-monitor/sessions/nonexistent_token_xyz/revoke")
        check("6. revoke bilinmeyen → 404", r.status_code == 404, f"status={r.status_code}")

        # 7. revoke Teacher → 403
        r = tc.post(f"/api/v2/admin/security-monitor/sessions/{seed['session_token']}/revoke")
        check("7. revoke Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 8. ips/block happy
        r = sc.post("/api/v2/admin/security-monitor/ips/block",
                    json={"ip": TEST_IP, "hours": 2, "note": "smoke"})
        j = r.json()
        ok = r.status_code == 200 and TEST_IP in j["data"]["message"] and "admin:security:overview" in j["invalidate"]
        check("8. ips/block happy", ok, f"status={r.status_code} {r.text[:120]}")

        # 9. boş ip → 400
        r = sc.post("/api/v2/admin/security-monitor/ips/block", json={"ip": "  ", "hours": 1})
        check("9. ips/block boş ip → 400", r.status_code == 400, f"status={r.status_code}")

        # 10. hours clamp (>720 → kabul 200)
        r = sc.post("/api/v2/admin/security-monitor/ips/block",
                    json={"ip": TEST_IP, "hours": 99999, "note": ""})
        check("10. ips/block hours clamp → 200", r.status_code == 200, f"status={r.status_code}")

        # 11. ips/unblock happy
        r = sc.post("/api/v2/admin/security-monitor/ips/unblock", json={"ip": TEST_IP})
        check("11. ips/unblock happy", r.status_code == 200 and TEST_IP in r.json()["data"]["message"],
              f"status={r.status_code}")

        # 12. unblock bilinmeyen → 404
        r = sc.post("/api/v2/admin/security-monitor/ips/unblock", json={"ip": "192.0.2.254"})
        check("12. ips/unblock bilinmeyen → 404", r.status_code == 404, f"status={r.status_code}")

        # 13. ips/block Teacher → 403
        r = tc.post("/api/v2/admin/security-monitor/ips/block", json={"ip": TEST_IP, "hours": 1})
        check("13. ips/block Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 14. impersonation end happy
        r = sc.post(f"/api/v2/admin/security-monitor/impersonations/{seed['imp_id']}/end")
        j = r.json()
        ok = r.status_code == 200 and "admin:security:overview" in j["invalidate"]
        check("14. impersonation end happy", ok, f"status={r.status_code} {r.text[:120]}")
        with SessionLocal() as db:
            imp = db.get(ImpersonationSession, seed["imp_id"])
            check("14b. impersonation ended + reason", imp is not None and imp.ended_at is not None and imp.end_reason == "revoked", "")

        # 15. impersonation end bilinmeyen → 404
        r = sc.post("/api/v2/admin/security-monitor/impersonations/99999999/end")
        check("15. impersonation end bilinmeyen → 404", r.status_code == 404, f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
