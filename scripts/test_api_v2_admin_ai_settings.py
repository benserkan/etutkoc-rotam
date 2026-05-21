"""API v2 /admin/settings/ai smoke — Gemini AI ayarları (tek sağlayıcı).

Senaryolar:
   1. Anonim GET → 401
   2. Teacher GET → 403
   3. Super GET → 4 item (2 secret key + 2 model)
   4. POST geçersiz ad → 400 invalid_setting
   5. POST boş value → 400 empty_value
   6. POST gemini_paid_api_key → kind=secret, source=db, maskeli (düz değer dönmez)
   7. şifreleme roundtrip + get_gemini_paid_key() == değer
   8. POST gemini_paid_model = özel → kind=config, value DÜZ döner
   9. get_gemini_model(paid=True) == özel model
  10. gemini_free_api_key set → get_gemini_free_keys() == [değer]
  11. delete gemini_paid_api_key → source none/env
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import SystemSecret, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2ai{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
T_EMAIL = f"{PFX}_t@test.invalid"
PASSWORD = "AiSetPass1!@xyz"
PAID_KEY = "AIzaSyPAID-" + secrets.token_hex(10)
FREE_KEY = "AIzaSyFREE-" + secrets.token_hex(10)
MODEL = "gemini-2.5-pro-test"

NAMES = ("gemini_paid_api_key", "gemini_free_api_key", "gemini_paid_model", "gemini_free_model")

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


def _wipe_secrets():
    with SessionLocal() as db:
        db.execute(sa_delete(SystemSecret).where(SystemSecret.name.in_(NAMES)))
        db.commit()


def _cleanup(seed):
    with SessionLocal() as db:
        _wipe_secrets()
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
    print(f"\n=== API v2 /admin AI settings smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    _wipe_secrets()
    seed = _seed()
    URL = "/api/v2/admin/settings/ai"
    try:
        r = TestClient(app).get(URL)
        check("1. Anonim GET → 401", r.status_code == 401, f"status={r.status_code}")

        tc = _login(T_EMAIL)
        r = tc.get(URL)
        check("2. Teacher GET → 403", r.status_code == 403, f"status={r.status_code}")

        sc = _login(SUPER_EMAIL)
        r = sc.get(URL)
        names = {it["name"] for it in r.json().get("items", [])}
        check("3. Super GET → 4 item", r.status_code == 200 and names == set(NAMES), f"status={r.status_code} {names}")

        r = sc.post(URL, json={"name": "bad_name", "value": "x"})
        check("4. geçersiz ad → 400", r.status_code == 400 and r.json()["detail"]["code"] == "invalid_setting", f"status={r.status_code}")

        r = sc.post(URL, json={"name": "gemini_paid_api_key", "value": "  "})
        check("5. boş value → 400", r.status_code == 400 and r.json()["detail"]["code"] == "empty_value", f"status={r.status_code}")

        r = sc.post(URL, json={"name": "gemini_paid_api_key", "value": PAID_KEY})
        item = next((it for it in r.json()["data"]["items"] if it["name"] == "gemini_paid_api_key"), {})
        check("6. paid key set → secret/db/maskeli",
              r.status_code == 200 and item.get("kind") == "secret" and item.get("source") == "db"
              and item.get("value") and PAID_KEY not in item.get("value", ""), f"{item}")

        from app.services.system_secrets import get_db_value, get_gemini_model, get_gemini_paid_key, get_gemini_free_keys
        with SessionLocal() as db:
            row = db.query(SystemSecret).filter(SystemSecret.name == "gemini_paid_api_key").first()
            enc_ok = row is not None and PAID_KEY not in (row.value_encrypted or "")
            dec_ok = get_db_value(db, "gemini_paid_api_key") == PAID_KEY
        check("7. şifreli saklanır + çözülür + resolve",
              enc_ok and dec_ok and get_gemini_paid_key() == PAID_KEY, f"enc={enc_ok} dec={dec_ok}")

        r = sc.post(URL, json={"name": "gemini_paid_model", "value": MODEL})
        item = next((it for it in r.json()["data"]["items"] if it["name"] == "gemini_paid_model"), {})
        check("8. model set → config/düz değer", item.get("kind") == "config" and item.get("value") == MODEL, f"{item}")

        check("9. get_gemini_model(paid) == özel", get_gemini_model(paid=True) == MODEL, f"{get_gemini_model(paid=True)}")

        sc.post(URL, json={"name": "gemini_free_api_key", "value": FREE_KEY})
        check("10. get_gemini_free_keys() == [free]", get_gemini_free_keys() == [FREE_KEY], "liste eşleşmedi")

        r = sc.post(f"{URL}/gemini_paid_api_key/delete")
        with SessionLocal() as db:
            gone = db.query(SystemSecret).filter(SystemSecret.name == "gemini_paid_api_key").first() is None
        check("11. delete → DB'den silindi", r.status_code == 200 and gone, f"status={r.status_code} gone={gone}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
