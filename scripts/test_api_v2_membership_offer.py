"""WhatsApp Üyelik Teklifi (MembershipOffer, Paket 1) smoke.

Senaryolar:
  1. anon bilinmeyen token → valid=false + not_found
  2. süper admin teklif oluştur (hedef koç, new, solo_pro, monthly) → token+public_url
  3. teacher (admin değil) oluşturamaz → 403
  4. anon GET teklif → valid + active + plan_label + amount + target_name + viewed
  5. havale KALDIRILDI — public GET yanıtında havale alanı yok (tek ödeme: iyzico kart)
  6. admin /havale ayar ucu kaldırıldı → 404/405
  7. anon POST /request → ContactRequest(source=membership_offer) + offer accepted/requested (lead)
  8. anon POST /havale-claim ucu kaldırıldı → 404/405
  9. (havale akışı tamamen kaldırıldı)
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

        # 5. havale KALDIRILDI → public GET yanıtında havale alanı yok (kart-only)
        r = anon.get(f"/api/v2/membership/{token}")
        check("5. public GET → havale alanı yok (tek ödeme: iyzico kart)",
              r.status_code == 200 and "havale" not in (r.json() or {}),
              f"{r.status_code}")

        # 6. admin havale ayar ucu KALDIRILDI → 404/405
        r = admin.post("/api/v2/admin/membership-offers/havale", json={"iban": "TR1"})
        check("6. admin /havale ayar ucu kaldırıldı → 404/405",
              r.status_code in (404, 405), f"{r.status_code}")

        # 7. request (lead — ödeme değil, iletişim)
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

        # 8. havale-claim ucu KALDIRILDI → 404/405 (tek ödeme: iyzico kart)
        r = admin.post("/api/v2/admin/membership-offers", json={
            "target_user_id": cid, "offer_type": "renewal", "plan_code": "solo_elite",
            "cycle": "annual"})
        token2 = r.json()["token"]
        r = anon.post(f"/api/v2/membership/{token2}/havale-claim", json={})
        check("8. /havale-claim ucu kaldırıldı → 404/405",
              r.status_code in (404, 405), f"{r.status_code}")

        # 9. (havale akışı tamamen kaldırıldı — kart-only)

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

        # 12. audience — solo_free koç "free" grubunda görünür
        r = admin.get("/api/v2/admin/membership-offers/audience")
        groups = (r.json() or {}).get("groups", []) if r.status_code == 200 else []
        free = next((g for g in groups if g["key"] == "free"), None)
        check("12. audience → free grubunda test koçu var",
              free is not None and any(m["id"] == cid for m in free["members"]),
              f"{r.status_code} groups={[g['key'] for g in groups]}")

        # 13. bulk create (koça birer teklif)
        r = admin.post("/api/v2/admin/membership-offers/bulk", json={
            "target_user_ids": [cid], "offer_type": "renewal", "plan_code": "solo_pro",
            "cycle": "monthly"})
        ok = r.status_code == 200
        bd = r.json() if ok else {}
        check("13. bulk → created=1 + token + public_url",
              ok and bd.get("created") == 1 and bd["items"][0].get("token")
              and "/membership/" in bd["items"][0].get("public_url", ""),
              f"{r.status_code} {r.text[:160]}")

        # 14. bulk boş hedef → 422
        r = admin.post("/api/v2/admin/membership-offers/bulk", json={
            "target_user_ids": [], "plan_code": "solo_pro", "offer_type": "new", "cycle": "monthly"})
        check("14. bulk boş hedef → 422 no_targets",
              r.status_code == 422 and _code(r) == "no_targets", f"{r.status_code}")

        # 15. teacher bulk yapamaz → 403
        r = coach.post("/api/v2/admin/membership-offers/bulk", json={
            "target_user_ids": [cid], "plan_code": "solo_pro", "offer_type": "new", "cycle": "monthly"})
        check("15. teacher bulk → 403", r.status_code == 403, f"{r.status_code}")

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
