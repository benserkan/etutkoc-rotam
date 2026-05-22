"""API v2 /admin/settings/pricing smoke — süper admin üyelik/fiyat override (M2).

Senaryolar:
   1. Anonim GET → 401
   2. Teacher GET → 403
   3. Super GET → config + defaults (solo_bands, institution_tiers)
   4. POST override (solo 6-15 bandı 4500) → kaydedilir
   5. /api/v2/pricing (public) override'ı yansıtır + compute_solo_monthly güncel
   6. POST geçersiz (boş band) → 400
   7. reset → defaults'a döner (15 öğr tekrar 4000)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import copy
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import AppSetting, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.services import pricing

PFX = f"v2pr{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
T_EMAIL = f"{PFX}_t@test.invalid"
PASSWORD = "PrcPass1!@xyz"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed():
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        sup = User(email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
                   role=UserRole.SUPER_ADMIN, is_active=True)
        t = User(email=T_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([sup, t]); db.flush()
        out = {"sup_id": sup.id, "t_id": t.id}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        db.execute(sa_delete(AppSetting).where(AppSetting.key == "pricing"))
        db.execute(sa_delete(User).where(User.id.in_([seed["sup_id"], seed["t_id"]])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== API v2 /admin pricing smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
        db.execute(sa_delete(AppSetting).where(AppSetting.key == "pricing")); db.commit()
    seed = _seed()
    URL = "/api/v2/admin/settings/pricing"
    try:
        r = TestClient(app).get(URL)
        check("1. Anonim GET → 401", r.status_code == 401, f"status={r.status_code}")

        tc = _login(T_EMAIL)
        r = tc.get(URL)
        check("2. Teacher GET → 403", r.status_code == 403, f"status={r.status_code}")

        sc = _login(SUPER_EMAIL)
        r = sc.get(URL)
        j = r.json()
        check("3. Super GET → config + defaults",
              r.status_code == 200 and len(j["config"]["solo_bands"]) == 3
              and len(j["config"]["institution_tiers"]) == 3
              and j["defaults"]["solo_bands"][1]["monthly"] == 4000, f"{r.text[:160]}")

        # 4. override: 6-15 bandını 4500 yap
        cfg = copy.deepcopy(j["config"])
        cfg["solo_bands"][1]["monthly"] = 4500
        r = sc.post(URL, json=cfg)
        check("4. POST override → 200", r.status_code == 200
              and r.json()["data"]["config"]["solo_bands"][1]["monthly"] == 4500, f"status={r.status_code} {r.text[:160]}")

        # 5. public /pricing + calculator override'ı yansıtır
        r = TestClient(app).get("/api/v2/pricing")
        pub_ok = r.status_code == 200 and r.json()["solo"]["bands"][1]["monthly"] == 4500
        calc_ok = pricing.compute_solo_monthly(15) == 4500
        check("5. public /pricing + compute override yansır", pub_ok and calc_ok,
              f"pub={pub_ok} calc={pricing.compute_solo_monthly(15)}")

        # 6. geçersiz: boş band
        bad = copy.deepcopy(cfg); bad["solo_bands"] = []
        r = sc.post(URL, json=bad)
        check("6. boş band → 400", r.status_code == 400 and r.json()["detail"]["code"] == "invalid_pricing", f"status={r.status_code}")

        # 7. reset → default
        r = sc.post(f"{URL}/reset")
        check("7. reset → 200 + default", r.status_code == 200
              and r.json()["data"]["config"]["solo_bands"][1]["monthly"] == 4000, f"status={r.status_code}")
        check("7b. calculator default'a döndü", pricing.compute_solo_monthly(15) == 4000,
              f"calc={pricing.compute_solo_monthly(15)}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
