"""API v2 — Mobil (RN) auth köprüsü smoke.

RN app cookie kullanamaz → token'lar GÖVDEDE döner (mobile=true), Bearer ile
/api/v2 tüketilir. Web BFF cookie davranışı KORUNUR (mobile=false → token
gövdede None, cookie kurulur).

Senaryolar:
  1. mobile login → 200 + access_token + refresh_token + user (gövdede)
  2. Bearer access → /api/v2/me 200
  3. /auth/token/refresh (gövde refresh) → yeni access; yeni access /me 200
  4. web login (mobile=false) → token'lar gövdede None (cookie kurulur — eski davranış)
  5. geçersiz refresh → 401
  6. must_change kullanıcı → mobile login: must_change_password=true + access_token var
     (RN /me/password-change'e ulaşabilsin); o token'la /me → 403 password_change_required
  7. yanlış şifre → 401 (mobil)
"""
from __future__ import annotations

import sys
try:
    sys.path.insert(0, ".")
except Exception:
    pass
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"aum_{secrets.token_hex(3)}"
PWDH = "Mobile!23456"
PWD = hash_password(PWDH)
now = datetime.now(timezone.utc)
ctx: dict = {}
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        t = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                 full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
                 is_active=True, plan="solo_pro", password_changed_at=now,
                 must_change_password=False)
        mc = User(email=f"{PFX}_mc@test.invalid", password_hash=PWD,
                  full_name=f"{PFX} MC", role=UserRole.TEACHER, institution_id=None,
                  is_active=True, plan="solo_pro", password_changed_at=now,
                  must_change_password=True)
        db.add(t); db.add(mc); db.flush()
        ctx.update(coach=t.id, mc=mc.id)
        db.commit()


def cleanup():
    with SessionLocal() as db:
        ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
        if ids:
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def mobile_login(c, suffix, pwd=PWDH):
    get_login_limiter().reset()
    return c.post("/api/v2/auth/login",
                  json={"email": f"{PFX}_{suffix}@test.invalid", "password": pwd, "mobile": True})


def main() -> int:
    print(f"\n=== MOBİL AUTH KÖPRÜSÜ — {PFX} ===\n")
    setup()
    try:
        c = TestClient(app)

        # 1. mobile login → token gövdede
        r = mobile_login(c, "coach")
        d = r.json() if r.status_code == 200 else {}
        access = d.get("access_token")
        refresh = d.get("refresh_token")
        check("1. mobile login → 200 + access+refresh+user gövdede",
              r.status_code == 200 and access and refresh and d.get("user") is not None
              and d.get("access_expires_in") and d.get("refresh_expires_in"),
              f"{r.status_code} {r.text[:160]}")

        # 2. Bearer access → /me 200 (cookie YOK; sadece header)
        bare = TestClient(app)
        r = bare.get("/api/v2/me", headers={"Authorization": f"Bearer {access}"})
        check("2. Bearer access → /api/v2/me 200", r.status_code == 200,
              f"{r.status_code} {r.text[:120]}")

        # 3. token/refresh (gövde) → yeni access çalışır
        r = bare.post("/api/v2/auth/token/refresh", json={"refresh_token": refresh})
        nd = r.json() if r.status_code == 200 else {}
        new_access = nd.get("access_token")
        # NOT: aynı saniyede üretilirse JWT iat aynı → token string birebir aynı
        # olabilir (geçerli, taze token); 3b çalıştığını doğrular.
        check("3a. token/refresh → 200 + access döner",
              r.status_code == 200 and bool(new_access),
              f"{r.status_code} {r.text[:120]}")
        r = bare.get("/api/v2/me", headers={"Authorization": f"Bearer {new_access}"})
        check("3b. yeni access → /me 200", r.status_code == 200, f"{r.status_code}")

        # 4. web login (mobile=false) → token gövdede YOK (cookie davranışı korunur)
        get_login_limiter().reset()
        wc = TestClient(app)
        r = wc.post("/api/v2/auth/login",
                    json={"email": f"{PFX}_coach@test.invalid", "password": PWDH})
        wd = r.json() if r.status_code == 200 else {}
        has_cookie = settings_access_cookie_present(wc)
        check("4. web login → token gövdede None + cookie kuruldu (eski davranış)",
              r.status_code == 200 and wd.get("access_token") is None
              and wd.get("user") is not None and has_cookie,
              f"{r.status_code} body_access={wd.get('access_token')} cookie={has_cookie}")

        # 5. geçersiz refresh → 401
        r = bare.post("/api/v2/auth/token/refresh", json={"refresh_token": "garbage.token.value"})
        check("5. geçersiz refresh → 401", r.status_code == 401, f"{r.status_code}")

        # 6. must_change → mobile login: must_change=true + access var; /me → 403
        r = mobile_login(c, "mc")
        md = r.json() if r.status_code == 200 else {}
        mc_access = md.get("access_token")
        check("6a. must_change mobile login → must_change_password=true + access var",
              r.status_code == 200 and md.get("must_change_password") is True and mc_access,
              f"{r.status_code} {r.text[:140]}")
        r = bare.get("/api/v2/me", headers={"Authorization": f"Bearer {mc_access}"})
        is_403 = r.status_code == 403 and r.json().get("detail", {}).get("code") == "password_change_required"
        check("6b. must_change access → /me 403 password_change_required", is_403,
              f"{r.status_code} {r.text[:140]}")

        # 7. yanlış şifre (mobil) → 401
        r = mobile_login(c, "coach", pwd="WRONGpwd!9")
        check("7. yanlış şifre mobil → 401", r.status_code == 401, f"{r.status_code}")
    finally:
        cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


def settings_access_cookie_present(client: TestClient) -> bool:
    from app.config import settings
    return settings.auth_cookie_access_name in client.cookies


if __name__ == "__main__":
    raise SystemExit(main())
