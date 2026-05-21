"""API v2 P5 — Oturum yönetimi + public teklif smoke (Dalga 7 P5).

Senaryolar:
   1. /me/sessions — login sonrası 1 oturum + is_current=True
   2. /me/sessions Anonim → 401
   3. ikinci login → /me/sessions 2 oturum
   4. /me/sessions/{token}/revoke — başka cihazı kapat → 200
   5. revoke sonrası kapatılan oturum cookie'siyle istek → 401 session_terminated
   6. revoke başkasının token'ı (sahte) → 404
   7. offers/{token} public view — geçerli teklif → valid=True + kind_label
   8. offers/{token} bilinmeyen → valid=False not_found
   9. offers/{token}/accept → 200 ok + accepted
  10. offers/{token}/accept tekrar → ok=False not_open
  11. offers/{token2}/decline → 200 declined
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import (
    ActiveSession,
    AuditLog,
    Institution,
    Offer,
    OfferKind,
    OfferStatus,
    SuspiciousIp,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2authp5_{_secrets.token_hex(3)}"
EMAIL = f"{PFX}@test.invalid"
PASSWORD = "UserPass1!@xyz"
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
    with SessionLocal() as db:
        u = User(
            email=EMAIL, password_hash=hash_password(PASSWORD), full_name=f"{PFX} User",
            role=UserRole.INSTITUTION_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False, email_verified_at=now,
        )
        inst = Institution(
            name=f"{PFX} Kurum", slug=f"{PFX}-kurum",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add_all([u, inst])
        db.flush()
        offer1 = Offer(
            owner_type="institution", institution_id=inst.id,
            token=f"{PFX}_off1_{_secrets.token_hex(5)}",
            kind=OfferKind.DISCOUNT_PERCENT, value=20, duration_months=3,
            title="%20 indirim", public_message="Size özel teklif",
            status=OfferStatus.SENT, expires_at=now + timedelta(days=7),
            sent_at=now,
        )
        offer2 = Offer(
            owner_type="institution", institution_id=inst.id,
            token=f"{PFX}_off2_{_secrets.token_hex(5)}",
            kind=OfferKind.TRIAL_EXTENSION, value=14,
            title="14 gün ek deneme",
            status=OfferStatus.SENT, expires_at=now + timedelta(days=7),
            sent_at=now,
        )
        db.add_all([offer1, offer2])
        db.flush()
        out = {"uid": u.id, "inst_id": inst.id, "off1": offer1.token,
               "off2": offer2.token, "off1_id": offer1.id, "off2_id": offer2.id}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(Offer).where(Offer.id.in_([seed["off1_id"], seed["off2_id"]])))
        db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id == seed["uid"]))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id == seed["uid"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id == seed["uid"]))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login() -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 P5 (oturum + teklif) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded uid={seed['uid']} off1={seed['off1'][:14]}…\n")

    try:
        # 1. /me/sessions login sonrası 1 oturum + current
        c1 = _login()
        r = c1.get("/api/v2/me/sessions")
        j = r.json()
        ok = r.status_code == 200 and len(j["sessions"]) == 1 and j["sessions"][0]["is_current"] is True
        check("1. /me/sessions 1 oturum + is_current", ok, f"status={r.status_code} {r.text[:120]}")

        # 2. anonim → 401
        r = TestClient(app).get("/api/v2/me/sessions")
        check("2. /me/sessions anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. ikinci login → 2 oturum
        c2 = _login()
        r = c1.get("/api/v2/me/sessions")
        j = r.json()
        check("3. ikinci login → 2 oturum", r.status_code == 200 and len(j["sessions"]) == 2,
              f"count={len(j['sessions'])}")
        # c2'nin token'ını bul (c1'den bakınca is_current=False olan)
        other = next((s for s in j["sessions"] if not s["is_current"]), None)
        check("3b. diğer oturum tespit edildi", other is not None, "")
        other_token = other["session_token"] if other else None

        # 4. revoke diğer cihaz
        r = c1.post(f"/api/v2/me/sessions/{other_token}/revoke")
        check("4. revoke diğer cihaz → 200", r.status_code == 200, f"status={r.status_code} {r.text[:100]}")

        # 5. kapatılan oturum (c2) cookie'siyle istek → 401 session_terminated
        r = c2.get("/api/v2/me")
        body = r.json() if r.text else {}
        check("5. kapatılan oturum → 401 session_terminated",
              r.status_code == 401 and body.get("detail", {}).get("code") == "session_terminated",
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # 6. revoke sahte token → 404
        r = c1.post("/api/v2/me/sessions/sahte_token_xyz/revoke")
        check("6. revoke sahte token → 404", r.status_code == 404, f"status={r.status_code}")

        # 7. offers view geçerli
        r = TestClient(app).get(f"/api/v2/offers/{seed['off1']}")
        j = r.json()
        ok = r.status_code == 200 and j.get("valid") is True and j.get("kind_label") and j.get("summary")
        check("7. offers view geçerli → valid + kind_label", ok, f"status={r.status_code} {j}")

        # 8. offers bilinmeyen
        r = TestClient(app).get("/api/v2/offers/bilinmeyen_token_xyz")
        j = r.json()
        check("8. offers bilinmeyen → not_found", r.status_code == 200 and j.get("valid") is False and j.get("status") == "not_found",
              f"{j}")

        # 9. accept
        r = TestClient(app).post(f"/api/v2/offers/{seed['off1']}/accept")
        j = r.json()
        check("9. offers accept → ok accepted", r.status_code == 200 and j.get("ok") is True and j.get("status") == "accepted",
              f"status={r.status_code} {j}")

        # 10. accept tekrar → not_open
        r = TestClient(app).post(f"/api/v2/offers/{seed['off1']}/accept")
        j = r.json()
        check("10. accept tekrar → ok=False not_open", r.status_code == 200 and j.get("ok") is False and j.get("status") == "not_open",
              f"{j}")

        # 11. decline (off2)
        r = TestClient(app).post(f"/api/v2/offers/{seed['off2']}/decline", json={"reason": "İlgilenmiyorum"})
        j = r.json()
        check("11. offers decline → declined", r.status_code == 200 and j.get("ok") is True and j.get("status") == "declined",
              f"{j}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
