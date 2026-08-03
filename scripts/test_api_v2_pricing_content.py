# -*- coding: utf-8 -*-
"""Faz 2A — kart içeriklerinin kodsuz yönetimi (pricing_content override).

Kapsam: süper admin GET/POST/reset · override'ın /api/v2/pricing kataloğuna
ANINDA yansıması (deploy'suz) · doğrulamalar (boş liste 400, /static dışı
görsel 400) · biçim/sözlük-senkron uyarıları · rol kapısı (koç 403).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import copy
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import SuspiciousIp, User, UserRole
from app.models.app_setting import AppSetting
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"pcont{secrets.token_hex(3)}"
PASSWORD = "PContent!2026X"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def main() -> int:
    print(f"\n=== Kart içerikleri kodsuz yönetim smoke — {PFX} ===\n")
    with SessionLocal() as db:
        sa_ = User(email=f"{PFX}-sa@t.invalid", password_hash=hash_password(PASSWORD),
                   full_name="Süper", role=UserRole.SUPER_ADMIN, is_active=True,
                   must_change_password=False)
        t = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                 full_name="Koç", role=UserRole.TEACHER, is_active=True,
                 plan="solo_pro", must_change_password=False)
        db.add_all([sa_, t])
        db.commit()
        # Test öncesi olası override kalıntısını temizle
        db.execute(sa_delete(AppSetting).where(AppSetting.key == "pricing_content"))
        db.commit()

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    URL = "/api/v2/admin/settings/pricing-content"
    try:
        sc = TestClient(app)
        sc.post("/api/v2/auth/login", json={"email": f"{PFX}-sa@t.invalid", "password": PASSWORD})
        tc = TestClient(app)
        tc.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})

        r = TestClient(app).get(URL)
        check("1. anonim → 401", r.status_code == 401, str(r.status_code))
        r = tc.get(URL)
        check("2. koç → 403", r.status_code == 403, str(r.status_code))

        r = sc.get(URL)
        j = r.json()
        check("3. GET → config + defaults + warnings",
              r.status_code == 200 and "tier_new" in j["config"]
              and "glossary" in j["defaults"] and isinstance(j["warnings"], list),
              r.text[:150])
        check("3b. varsayılanda biçim uyarısı yok", j["warnings"] == [], str(j["warnings"]))

        # 4. Override: Patika'ya yeni madde + tagline + sözlük terimi
        cfg = copy.deepcopy(j["config"])
        cfg["tier_new"]["solo_pro"].append("Deneme Özelliği — kodsuz eklendi")
        cfg["taglines"]["solo_elite"] = "Test tagline (override)"
        cfg["glossary"].append({"term": "Deneme Özelliği",
                                "explanation": "Kodsuz yönetim smoke terimi.",
                                "image": None, "image_w": None, "image_h": None,
                                "image_full": None})
        r = sc.post(URL, json=cfg)
        check("4. POST override → 200 + uyarısız", r.status_code == 200
              and r.json()["data"]["warnings"] == [], r.text[:200])

        # 5. Katalog ANINDA yansıtır (deploy'suz — kodsuz yönetimin kanıtı)
        r = TestClient(app).get("/api/v2/pricing")
        cat = r.json()
        pat = [c for c in cat["cards"] if c["plan"] == "solo_pro"][0]
        rота = [c for c in cat["cards"] if c["plan"] == "solo_elite"][0]
        check("5. katalog: yeni madde + tagline + sözlük",
              "Deneme Özelliği — kodsuz eklendi" in pat["features"]
              and rота["tagline"] == "Test tagline (override)"
              and any(g["term"] == "Deneme Özelliği" for g in cat["feature_glossary"]),
              str(pat["features"][-1:]) + rота["tagline"])
        check("5b. kümülatif liste de yansır (plan_features)",
              "Deneme Özelliği — kodsuz eklendi" in cat["plan_features"]["solo_unlimited"])

        # 6. Uyarılar: uzun ayraçsız madde + maddede geçmeyen sözlük terimi
        bad = copy.deepcopy(cfg)
        bad["tier_new"]["solo_pro"].append(
            "Bu çok uzun bir cümle maddesidir ve ayraç kullanılmadığı için kart duvara döner")
        bad["glossary"].append({"term": "Hayalet Terim",
                                "explanation": "Hiçbir maddede geçmiyor.",
                                "image": None, "image_w": None, "image_h": None,
                                "image_full": None})
        r = sc.post(URL, json=bad)
        w = r.json()["data"]["warnings"]
        check("6. tavsiye uyarıları (bloklamadan)", r.status_code == 200
              and any("Madde biçimi" in x for x in w)
              and any("Hayalet Terim" in x for x in w), str(w))

        # 7. Doğrulama: boş listeler 400 · /static dışı görsel 400
        empty = copy.deepcopy(cfg); empty["free_features"] = []
        r = sc.post(URL, json=empty)
        check("7. boş liste → 400 invalid_content", r.status_code == 400
              and r.json()["detail"]["code"] == "invalid_content", str(r.status_code))
        evil = copy.deepcopy(cfg)
        evil["glossary"][0]["image"] = "https://evil.example/x.png"
        r = sc.post(URL, json=evil)
        check("7b. /static dışı görsel → 400", r.status_code == 400, str(r.status_code))

        # 8. Reset → kod varsayılanı; katalog eski hâline döner
        r = sc.post(f"{URL}/reset")
        check("8. reset → 200", r.status_code == 200, str(r.status_code))
        r = TestClient(app).get("/api/v2/pricing")
        pat = [c for c in r.json()["cards"] if c["plan"] == "solo_pro"][0]
        check("8b. katalog varsayılana döndü",
              "Deneme Özelliği — kodsuz eklendi" not in pat["features"])
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(AppSetting).where(AppSetting.key == "pricing_content"))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}-%")))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f_ in failed:
        print("  FAIL:", f_)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
