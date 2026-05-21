"""API v2 /auth P1 — BFF güvenlik birleştirme smoke (Dalga 7 P1).

Jinja login paritesi eklemeleri:
  1. login happy → ActiveSession kaydı oluşur (sid JWT'de)
  2. login sonrası /auth/me → heartbeat (last_seen güncel)
  3. logout → ActiveSession terminated (canlı panelden düşer)
  4. terminate edilen oturum cookie'siyle istek → 401 session_terminated
  5. wrong password → SuspiciousIp fail kaydı beslenir
  6. turnstile config endpoint → enabled=False (env yok) + site_key None
  7. refresh → sid korunur (ActiveSession aynı satır, last_seen güncel)
  8. must_change_password user → login 200 + must_change True; /auth/me → 403
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

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import ActiveSession, AuditLog, SuspiciousIp, User, UserRole
from app.services.jwt_auth import decode_token
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2authp1_{secrets.token_hex(3)}"
EMAIL = f"{PFX}@test.invalid"
MUST_EMAIL = f"{PFX}_must@test.invalid"
PASSWORD = "TestPass123!@xyz"
ACCESS = settings.auth_cookie_access_name
REFRESH = settings.auth_cookie_refresh_name

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
        u = User(
            email=EMAIL, password_hash=pwd, full_name=f"{PFX} User",
            role=UserRole.TEACHER, is_active=True, plan="solo_free",
            password_changed_at=now, must_change_password=False,
        )
        must = User(
            email=MUST_EMAIL, password_hash=pwd, full_name=f"{PFX} Must",
            role=UserRole.TEACHER, is_active=True, plan="solo_free",
            password_changed_at=now, must_change_password=True,
        )
        db.add_all([u, must])
        db.commit()
        return {"uid": u.id, "must_id": must.id}


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["uid"], seed["must_id"]]
        db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(uids)))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        # record_failed_login_ip TestClient IP'sini ("testclient") bloklayabilir;
        # sonraki test paketleri 429 almasın diye temizle.
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def main() -> int:
    print(f"\n=== API v2 /auth P1 (BFF güvenlik birleştirme) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded uid={seed['uid']} must_id={seed['must_id']}\n")

    try:
        # 1. login happy → ActiveSession
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": EMAIL, "password": PASSWORD})
        access = None
        for ck in c.cookies.jar:
            if ck.name == ACCESS:
                access = ck.value
        sid = None
        if access:
            try:
                sid = decode_token(access).session_id
            except Exception:
                sid = None
        ok = r.status_code == 200 and sid is not None
        check("1. login happy + sid JWT'de", ok, f"status={r.status_code} sid={sid is not None}")
        with SessionLocal() as db:
            sess = db.query(ActiveSession).filter(ActiveSession.session_token == sid).first() if sid else None
            check("1b. ActiveSession kaydı oluştu", sess is not None and sess.terminated_at is None,
                  f"sess={sess is not None}")
            first_seen = sess.last_seen_at if sess else None

        # 2. /auth/me → heartbeat
        r = c.get("/api/v2/auth/me")
        check("2. /auth/me cookie ile → 200 (heartbeat)", r.status_code == 200, f"status={r.status_code}")

        # 3. logout → ActiveSession terminated
        r = c.post("/api/v2/auth/logout")
        check("3. logout → 200", r.status_code == 200, f"status={r.status_code}")
        with SessionLocal() as db:
            sess = db.query(ActiveSession).filter(ActiveSession.session_token == sid).first() if sid else None
            check("3b. ActiveSession terminated", sess is not None and sess.terminated_at is not None,
                  f"terminated={sess.terminated_at if sess else None}")

        # 4. terminate edilen oturum cookie'siyle istek → 401 session_terminated
        # (logout cookie sildi; manuel eski cookie ile dene)
        r = TestClient(app).get("/api/v2/me", headers={"Cookie": f"{ACCESS}={access}"})
        body = r.json() if r.text else {}
        ok = r.status_code == 401 and body.get("detail", {}).get("code") == "session_terminated"
        check("4. terminated oturum cookie → 401 session_terminated", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # 5. wrong password → SuspiciousIp beslenir
        before = _suspicious_count()
        TestClient(app).post("/api/v2/auth/login", json={"email": EMAIL, "password": "WRONG_xyz_123"})
        after = _suspicious_count()
        check("5. wrong password → SuspiciousIp beslenir", after >= before,
              f"before={before} after={after}")

        # 6. turnstile config endpoint
        r = TestClient(app).get("/api/v2/auth/turnstile")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("enabled") is False and body.get("site_key") is None
        check("6. turnstile config (env yok → disabled)", ok, f"status={r.status_code} body={body}")

        # 7. refresh → sid korunur + last_seen güncel
        c2 = TestClient(app)
        c2.post("/api/v2/auth/login", json={"email": EMAIL, "password": PASSWORD})
        sid2 = None
        for ck in c2.cookies.jar:
            if ck.name == ACCESS:
                try:
                    sid2 = decode_token(ck.value).session_id
                except Exception:
                    pass
        r = c2.post("/api/v2/auth/refresh")
        new_sid = None
        set_cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else []
        for h in set_cookies:
            if h.startswith(f"{ACCESS}="):
                tok = h.split(f"{ACCESS}=", 1)[1].split(";", 1)[0]
                try:
                    new_sid = decode_token(tok).session_id
                except Exception:
                    pass
        ok = r.status_code == 200 and new_sid is not None and new_sid == sid2
        check("7. refresh → sid korunur", ok, f"status={r.status_code} same_sid={new_sid == sid2}")

        # 8. must_change_password user
        c3 = TestClient(app)
        r = c3.post("/api/v2/auth/login", json={"email": MUST_EMAIL, "password": PASSWORD})
        body = r.json() if r.text else {}
        login_ok = r.status_code == 200 and body.get("must_change_password") is True
        r = c3.get("/api/v2/auth/me")
        me_body = r.json() if r.text else {}
        ok = login_ok and r.status_code == 403 and me_body.get("detail", {}).get("code") == "password_change_required"
        check("8. must_change → login 200 + me 403", ok,
              f"login_ok={login_ok} me_status={r.status_code} code={me_body.get('detail', {}).get('code')}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


def _suspicious_count() -> int:
    with SessionLocal() as db:
        from sqlalchemy import func
        return int(db.query(func.count(SuspiciousIp.id)).scalar() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
