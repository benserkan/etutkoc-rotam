"""CANLI pricing akışı testi (:3000) — katalog + süper admin editör + koç /plan.

1. Anonim /api/v2/pricing → 5 kart + 3 solo tier + 3 kurum tier (yapı).
2. Süper admin: GET pricing config → POST değiştir → /pricing yansıdı mı → reset.
3. Koç /plan: farklı öğrenci sayılarında doğru tier önerilir + 4 seçenek.

Sonunda DB'yi orijinal haline getirir (reset). Şifrelere dokunmaz; geçici user.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"pf_{secrets.token_hex(3)}"
PWDH = "Pricing!2345"
PWD = hash_password(PWDH)
now = datetime.now(timezone.utc)
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


def login(email):
    # Sunucu içi-bellek login limiter'ı (10/dk per IP) bu süreçten reset edilemez;
    # 429 dönerse sunucunun verdiği retry_after kadar bekleyip bir kez yeniden dene.
    get_login_limiter().reset()
    c = httpx.Client(base_url=BASE, timeout=40.0, follow_redirects=False)
    for attempt in range(2):
        r = c.post("/api/v2/auth/login", json={"email": email, "password": PWDH})
        if r.status_code == 200:
            return c
        if r.status_code == 429 and attempt == 0:
            try:
                wait = int(r.json().get("detail", {}).get("retry_after_seconds", 60))
            except Exception:
                wait = 60
            time.sleep(min(wait + 1, 62))
            continue
        raise RuntimeError(f"login {email}: {r.status_code} {r.text[:160]}")
    raise RuntimeError(f"login {email}: rate limited")


def make_user(suffix, role, plan=None, seed_students=0):
    with SessionLocal() as db:
        u = User(email=f"{PFX}_{suffix}@t.invalid", password_hash=PWD, full_name=f"{PFX} {suffix}",
                 role=role, institution_id=None, is_active=True, plan=plan,
                 password_changed_at=now, must_change_password=False)
        db.add(u); db.flush()
        uid = u.id
        for i in range(seed_students):
            db.add(User(email=f"{PFX}_{suffix}_s{i}@t.invalid", password_hash=PWD,
                        full_name=f"O{i}", role=UserRole.STUDENT, teacher_id=uid,
                        institution_id=None, grade_level=8, is_active=True,
                        password_changed_at=now, must_change_password=False))
        db.commit()
    return f"{PFX}_{suffix}@t.invalid"


def main() -> int:
    print(f"\n=== CANLI PRICING AKIŞI — BASE={BASE} — {PFX} ===\n")
    anon = httpx.Client(base_url=BASE, timeout=40.0)
    admin_email = make_user("admin", UserRole.SUPER_ADMIN)

    try:
        # ── 1. Katalog yapısı ──
        print("1. Katalog yapısı (/api/v2/pricing):")
        cat = anon.get("/api/v2/pricing").json()
        cards = cat.get("cards", [])
        keys = {c["key"] for c in cards}
        check("5 kart (free + 3 solo + institution)",
              keys == {"free", "solo_pro", "solo_elite", "solo_unlimited", "institution"}, str(keys))
        solo_tiers = cat["solo"]["tiers"]
        check("3 solo tier, kapaklar 10/25/sınırsız",
              [t["max_students"] for t in solo_tiers] == [10, 25, None],
              str([t["max_students"] for t in solo_tiers]))
        check("solo tier fiyatları 2500/5000/7500",
              [t["monthly"] for t in solo_tiers] == [2500, 5000, 7500],
              str([t["monthly"] for t in solo_tiers]))
        inst_tiers = cat["institution"]["tiers"]
        check("3 kurum tier, toplam 10000/30000/None",
              [t["monthly_total"] for t in inst_tiers] == [10000, 30000, None],
              str([t["monthly_total"] for t in inst_tiers]))
        check("enterprise price_hidden=True",
              inst_tiers[-1]["price_hidden"] is True, str(inst_tiers[-1]))
        feat = next(c for c in cards if c["key"] == "solo_elite")
        check("Solo (elite) öne çıkan + 'En popüler' rozet",
              feat["highlight"] is True and feat["badge"] == "En popüler", str(feat.get("badge")))

        # ── 2. Süper admin editör round-trip ──
        print("\n2. Süper admin pricing editör round-trip:")
        ac = login(admin_email)
        r = ac.get("/api/v2/admin/settings/pricing")
        check("GET pricing config → 200", r.status_code == 200, f"{r.status_code}")
        cfg = r.json()["config"]
        check("config solo_tiers 3 + institution_tiers 3",
              len(cfg["solo_tiers"]) == 3 and len(cfg["institution_tiers"]) == 3, "")
        # Değiştir: solo_pro fiyatını 2750 yap
        mod = dict(cfg)
        mod["solo_tiers"] = [dict(t) for t in cfg["solo_tiers"]]
        mod["solo_tiers"][0]["monthly"] = 2750
        r = ac.post("/api/v2/admin/settings/pricing", json=mod)
        check("POST değişiklik → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        cat2 = anon.get("/api/v2/pricing").json()
        check("/pricing yeni fiyatı yansıttı (2750)",
              cat2["solo"]["tiers"][0]["monthly"] == 2750,
              str(cat2["solo"]["tiers"][0]["monthly"]))
        # Geçersiz: negatif fiyat reddedilir
        bad = dict(mod)
        bad["solo_tiers"] = [dict(t) for t in mod["solo_tiers"]]
        bad["solo_tiers"][0]["monthly"] = -5
        r = ac.post("/api/v2/admin/settings/pricing", json=bad)
        check("negatif fiyat → 400 invalid_pricing",
              r.status_code == 400, f"{r.status_code}")
        # Reset
        r = ac.post("/api/v2/admin/settings/pricing/reset")
        check("reset → 200", r.status_code == 200, f"{r.status_code}")
        cat3 = anon.get("/api/v2/pricing").json()
        check("reset sonrası fiyat default'a döndü (2500)",
              cat3["solo"]["tiers"][0]["monthly"] == 2500,
              str(cat3["solo"]["tiers"][0]["monthly"]))

        # ── 3. Koç /plan tier önerisi ──
        print("\n3. Koç /plan — öğrenci sayısına göre tier önerisi:")
        for suffix, count, expect in [("c5", 5, "solo_pro"), ("c18", 18, "solo_elite"), ("c40", 40, "solo_unlimited")]:
            e = make_user(suffix, UserRole.TEACHER, plan="solo_free", seed_students=count)
            r = login(e).get("/api/v2/teacher/plan")
            j = r.json()
            opt_codes = {o["code"] for o in j["options"]}
            check(f"{count} öğrenci → önerilen={expect} + 4 seçenek",
                  j["recommended_plan"] == expect and opt_codes == {"solo_free", "solo_pro", "solo_elite", "solo_unlimited"},
                  f"rec={j.get('recommended_plan')} opts={opt_codes}")
            rec_opt = next(o for o in j["options"] if o["code"] == expect)
            check(f"{count} öğrenci → önerilen seçenek is_recommended=True",
                  rec_opt["is_recommended"] is True, str(rec_opt))

    finally:
        # editör reset (testte fail olsa bile default'a döndür)
        try:
            login(admin_email).post("/api/v2/admin/settings/pricing/reset")
        except Exception:
            pass
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
