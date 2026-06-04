"""WhatsApp Üyelik Teklifi (MembershipOffer, Paket 1) smoke.

Senaryolar:
  1. anon bilinmeyen token → valid=false + not_found
  2. süper admin teklif oluştur (hedef koç, new, solo_pro, monthly) → token+public_url
  3. teacher (admin değil) oluşturamaz → 403
  4. anon GET teklif → valid + active + plan_label + amount + target_name + viewed
  5. havale ayarla (admin) → enabled
  6. anon GET → havale.enabled + iban
  7. anon POST /request → ContactRequest(source=membership_offer) + offer accepted/requested
  8. anon POST /havale-claim (yeni teklif) → completion=havale_claimed + ContactRequest
  9. havale kapalıyken /havale-claim → 400 havale_disabled
 10. geçersiz plan → 400 invalid_plan · olmayan hedef → 400 target_not_found
 11. olmayan token /request → 404
"""
from __future__ import annotations

import sys
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
from app.models import ContactRequest, MembershipOffer, User, UserRole
from app.services import app_settings
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.models.suspicious_ip import SuspiciousIp

PFX = f"moffer_{secrets.token_hex(3)}"
PWD = hash_password("MOffer!23")
PWDH = "MOffer!23"
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


def _code(r):
    try:
        return (r.json().get("detail", {}) or {}).get("code")
    except Exception:
        return None


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        admin = User(email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN,
                     is_active=True, password_changed_at=now, must_change_password=False)
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
                     is_active=True, plan="solo_free", password_changed_at=now,
                     must_change_password=False, phone="905321112233")
        db.add(admin); db.add(coach); db.flush()
        db.commit()
        ctx.update(admin=admin.id, coach=coach.id)


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code} {r.text[:120]}")
    return c


def main() -> int:
    print(f"\n=== WHATSAPP ÜYELİK TEKLİFİ (MembershipOffer) — {PFX} ===\n")
    setup()
    cid = ctx["coach"]
    anon = TestClient(app)
    try:
        # 1. bilinmeyen token
        r = anon.get("/api/v2/membership/yokboyle123")
        check("1. bilinmeyen token → valid=false + not_found",
              r.status_code == 200 and r.json()["valid"] is False
              and r.json()["status"] == "not_found", f"{r.status_code} {r.text[:120]}")

        admin = login("admin")
        coach = login("coach")

        # 3. teacher oluşturamaz
        r = coach.post("/api/v2/admin/membership-offers",
                       json={"plan_code": "solo_pro", "offer_type": "new", "cycle": "monthly"})
        check("3. teacher oluşturamaz → 403", r.status_code == 403, f"{r.status_code}")

        # 2. admin oluştur
        r = admin.post("/api/v2/admin/membership-offers", json={
            "target_user_id": cid, "offer_type": "new", "plan_code": "solo_pro",
            "cycle": "monthly"})
        ok = r.status_code == 200
        data = r.json() if ok else {}
        token = data.get("token")
        check("2. admin oluştur → 200 + token + public_url",
              ok and token and "/membership/" in (data.get("public_url") or ""),
              f"{r.status_code} {r.text[:160]}")

        # 4. anon GET
        r = anon.get(f"/api/v2/membership/{token}")
        v = r.json() if r.status_code == 200 else {}
        check("4. anon GET → active + plan_label + amount=2500 + target_name + features",
              r.status_code == 200 and v.get("valid") and v.get("status") == "active"
              and v.get("plan_label") and v.get("amount") == 2500
              and v.get("target_name", "").startswith(PFX) and len(v.get("plan_features") or []) > 0,
              f"{r.status_code} {v}")
        with SessionLocal() as db:
            o = db.query(MembershipOffer).filter(MembershipOffer.token == token).first()
            check("4b. viewed_at işaretlendi", o is not None and o.viewed_at is not None, "")

        # 5. havale ayarla
        r = admin.post("/api/v2/admin/membership-offers/havale", json={
            "iban": "TR12 0000 0000 0000 0000 0000 01", "name": "ETÜTKOÇ", "note": "Açıklamaya teklif no yaz"})
        check("5. havale ayarla → enabled", r.status_code == 200 and r.json()["enabled"] is True,
              f"{r.status_code} {r.text[:120]}")

        # 6. anon GET → havale görünür
        r = anon.get(f"/api/v2/membership/{token}")
        hav = (r.json() or {}).get("havale") or {}
        check("6. anon GET → havale.enabled + iban", hav.get("enabled") and "TR12" in hav.get("iban", ""),
              f"{hav}")

        # 7. request
        r = anon.post(f"/api/v2/membership/{token}/request", json={})
        check("7. /request → 200 ok + requested",
              r.status_code == 200 and r.json()["ok"] and r.json()["completion"] == "requested",
              f"{r.status_code} {r.text[:140]}")
        with SessionLocal() as db:
            cr = (db.query(ContactRequest)
                  .filter(ContactRequest.source == "membership_offer")
                  .order_by(ContactRequest.id.desc()).first())
            check("7b. ContactRequest(source=membership_offer) oluştu + koç_id var",
                  cr is not None and f"koç_id={cid}" in (cr.message or ""), f"{cr}")
            o = db.query(MembershipOffer).filter(MembershipOffer.token == token).first()
            check("7c. offer accepted + completion=requested",
                  o.status == "accepted" and o.completion == "requested", f"{o.status}/{o.completion}")

        # 8. havale-claim (yeni teklif)
        r = admin.post("/api/v2/admin/membership-offers", json={
            "target_user_id": cid, "offer_type": "renewal", "plan_code": "solo_elite",
            "cycle": "annual"})
        token2 = r.json()["token"]
        r = anon.post(f"/api/v2/membership/{token2}/havale-claim", json={"name": "Veli X", "phone": "905330001122"})
        check("8. /havale-claim → 200 + havale_claimed",
              r.status_code == 200 and r.json()["completion"] == "havale_claimed",
              f"{r.status_code} {r.text[:140]}")

        # 9. havale kapalıyken claim → 400
        admin.post("/api/v2/admin/membership-offers/havale", json={"iban": "", "name": "", "note": ""})
        r = admin.post("/api/v2/admin/membership-offers", json={
            "target_user_id": cid, "plan_code": "solo_pro", "offer_type": "new", "cycle": "monthly"})
        token3 = r.json()["token"]
        r = anon.post(f"/api/v2/membership/{token3}/havale-claim", json={})
        check("9. havale kapalı → 400 havale_disabled",
              r.status_code == 400 and _code(r) == "havale_disabled", f"{r.status_code}")

        # 10. validasyon
        r = admin.post("/api/v2/admin/membership-offers", json={
            "plan_code": "yokboyleplan", "offer_type": "new", "cycle": "monthly"})
        check("10a. geçersiz plan → 400 invalid_plan",
              r.status_code == 400 and _code(r) == "invalid_plan", f"{r.status_code}")
        r = admin.post("/api/v2/admin/membership-offers", json={
            "target_user_id": 99999999, "plan_code": "solo_pro", "offer_type": "new", "cycle": "monthly"})
        check("10b. olmayan hedef → 400 target_not_found",
              r.status_code == 400 and _code(r) == "target_not_found", f"{r.status_code}")

        # 11. olmayan token request
        r = anon.post("/api/v2/membership/yokboyle/request", json={})
        check("11. olmayan token /request → 404", r.status_code == 404, f"{r.status_code}")

    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                db.execute(sa_delete(MembershipOffer).where(MembershipOffer.target_user_id.in_(ids)))
                db.execute(sa_delete(MembershipOffer).where(MembershipOffer.created_by_admin_id.in_(ids)))
            db.execute(sa_delete(ContactRequest).where(ContactRequest.source == "membership_offer"))
            try:
                app_settings.delete(db, "membership_havale")
            except Exception:
                pass
            if ids:
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
