"""Kampanya / Genel Link (CampaignLink, Yol A) smoke.

Senaryolar:
  1. anon bilinmeyen token → valid=false + not_found
  2. teacher (admin değil) oluşturamaz → 403
  3. süper admin kampanya oluştur (solo_pro, monthly, amount=2000) → token + public_url + audience=coach
  4. anon GET kampanya → active + plan_label + amount=2000 + list_price=2500 + savings=500 + features + view_count arttı
  5. anon POST lead {ad, telefon} → 200 ok + SalesProspect(inbound) + ContactRequest(source=campaign_link, hedef_tip=koc, aday_id) + lead_count arttı
  6. anon POST lead aynı telefon (dedup) → 200 + prospect tekrar yaratılmaz + lead_count yine artar
  7. geçersiz telefon → 422 invalid_phone
  8. admin duraklat → paused → anon GET valid=false
  9. duraklatılmışta lead → 409 not_active
 10. admin liste → kampanya görünür + lead_count + view_count
 11. kurum hedefli kampanya (etut_standart) → audience=institution + lead kurum prospect + hedef_tip=kurum
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
from app.models import CampaignLink, ContactRequest, SalesProspect, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.models.suspicious_ip import SuspiciousIp

PFX = f"camp_{secrets.token_hex(3)}"
PWD = hash_password("Camp!23")
PWDH = "Camp!23"
# Test telefonları (gerçek kullanıcıyla çakışmasın diye nadir prefix)
PH1 = "905387770011"
PH2 = "905387770022"
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


def cleanup():
    with SessionLocal() as db:
        # contact requests + prospects (test telefonları) + kampanyalar + users
        db.execute(sa_delete(ContactRequest).where(ContactRequest.phone.in_([PH1, PH2])))
        db.execute(sa_delete(SalesProspect).where(SalesProspect.phone.in_([PH1, PH2])))
        db.query(CampaignLink).filter(CampaignLink.name.like(f"{PFX}%")).delete(
            synchronize_session=False)
        db.query(User).filter(User.email.like(f"{PFX}%")).delete(synchronize_session=False)
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == "testclient").delete(
            synchronize_session=False)
        db.commit()


def setup():
    get_login_limiter().reset()
    cleanup()
    with SessionLocal() as db:
        admin = User(email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN,
                     is_active=True, password_changed_at=now, must_change_password=False)
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
                     is_active=True, plan="solo_free", password_changed_at=now,
                     must_change_password=False)
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
    print(f"\n=== KAMPANYA LİNKİ (CampaignLink) — {PFX} ===\n")
    setup()
    anon = TestClient(app)
    try:
        # 1. bilinmeyen token
        r = anon.get("/api/v2/campaign/yokboyle999")
        check("1. bilinmeyen token → valid=false + not_found",
              r.status_code == 200 and r.json()["valid"] is False
              and r.json()["status"] == "not_found", f"{r.status_code} {r.text[:120]}")

        admin = login("admin")
        coach = login("coach")

        # 2. teacher oluşturamaz
        r = coach.post("/api/v2/admin/campaign-links",
                       json={"name": f"{PFX} x", "plan_code": "solo_pro"})
        check("2. teacher oluşturamaz → 403", r.status_code == 403, f"{r.status_code}")

        # 3. admin oluştur (solo_pro, monthly, amount=2000)
        r = admin.post("/api/v2/admin/campaign-links", json={
            "name": f"{PFX} Koç Kampanyası", "plan_code": "solo_pro",
            "cycle": "monthly", "amount": 2000})
        ok = r.status_code == 200
        d = r.json() if ok else {}
        token = d.get("token")
        check("3. admin oluştur → 200 + token + public_url + audience=coach",
              ok and token and "/kampanya/" in (d.get("public_url") or "")
              and d.get("audience") == "coach", f"{r.status_code} {r.text[:160]}")
        ctx["token"] = token

        # 4. anon GET kampanya
        r = anon.get(f"/api/v2/campaign/{token}")
        v = r.json() if r.status_code == 200 else {}
        check("4. anon GET → active + amount=2000 + list_price=2500 + savings=500 + features",
              r.status_code == 200 and v.get("valid") and v.get("status") == "active"
              and v.get("amount") == 2000 and v.get("list_price") == 2500
              and v.get("savings") == 500 and len(v.get("plan_features") or []) > 0,
              f"{r.status_code} {v}")
        with SessionLocal() as db:
            link = db.query(CampaignLink).filter(CampaignLink.token == token).first()
            check("4b. view_count arttı", link is not None and (link.view_count or 0) >= 1,
                  f"view_count={getattr(link, 'view_count', None)}")

        # 5. anon POST lead
        r = anon.post(f"/api/v2/campaign/{token}/lead",
                      json={"name": "Ahmet Aday", "phone": PH1})
        check("5. lead → 200 ok", r.status_code == 200 and r.json().get("ok") is True,
              f"{r.status_code} {r.text[:160]}")
        with SessionLocal() as db:
            pr = db.query(SalesProspect).filter(SalesProspect.phone == PH1).first()
            cr = db.query(ContactRequest).filter(ContactRequest.phone == PH1).first()
            link = db.query(CampaignLink).filter(CampaignLink.token == token).first()
            check("5b. SalesProspect(inbound, coach) oluştu",
                  pr is not None and pr.source == "inbound" and pr.kind == "coach", f"{pr}")
            check("5c. ContactRequest(campaign_link) + hedef_tip=koc + aday_id + tutar=2000",
                  cr is not None and cr.source == "campaign_link"
                  and "hedef_tip=koc" in (cr.message or "")
                  and (pr and f"aday_id={pr.id}" in (cr.message or ""))
                  and "tutar=2000" in (cr.message or ""), f"{cr.message if cr else None}")
            check("5d. lead_count arttı", link is not None and (link.lead_count or 0) >= 1,
                  f"lead_count={getattr(link, 'lead_count', None)}")

        # 6. aynı telefon dedup
        r = anon.post(f"/api/v2/campaign/{token}/lead",
                      json={"name": "Ahmet Aday Tekrar", "phone": PH1})
        with SessionLocal() as db:
            cnt = db.query(SalesProspect).filter(SalesProspect.phone == PH1).count()
            link = db.query(CampaignLink).filter(CampaignLink.token == token).first()
        check("6. aynı telefon dedup → 200 + tek prospect + lead_count=2",
              r.status_code == 200 and cnt == 1 and (link.lead_count or 0) >= 2,
              f"status={r.status_code} prospect_count={cnt} lead_count={getattr(link,'lead_count',None)}")

        # 7. geçersiz telefon (Pydantic min_length geçer ama normalize reddeder)
        r = anon.post(f"/api/v2/campaign/{token}/lead",
                      json={"name": "Geçersiz", "phone": "11112222"})
        check("7. geçersiz telefon → 422 invalid_phone",
              r.status_code == 422 and _code(r) == "invalid_phone", f"{r.status_code} {_code(r)}")

        # 8. duraklat
        link_id = d.get("id")
        r = admin.post(f"/api/v2/admin/campaign-links/{link_id}/status",
                       json={"status": "paused"})
        check("8a. admin duraklat → 200 + paused",
              r.status_code == 200 and r.json().get("status") == "paused", f"{r.status_code}")
        r = anon.get(f"/api/v2/campaign/{token}")
        check("8b. duraklatılmış anon GET → valid=false",
              r.status_code == 200 and r.json().get("valid") is False
              and r.json().get("status") == "paused", f"{r.json()}")

        # 9. duraklatılmışta lead
        r = anon.post(f"/api/v2/campaign/{token}/lead",
                      json={"name": "Geç Kaldı", "phone": PH2})
        check("9. duraklatılmışta lead → 409 not_active",
              r.status_code == 409 and _code(r) == "not_active", f"{r.status_code} {_code(r)}")

        # 10. admin liste
        r = admin.get("/api/v2/admin/campaign-links")
        items = r.json().get("items", []) if r.status_code == 200 else []
        mine = next((x for x in items if x["token"] == token), None)
        check("10. admin liste → kampanya + lead_count>=2 + view_count>=1 + plan_options",
              mine is not None and mine["lead_count"] >= 2 and mine["view_count"] >= 1
              and len(r.json().get("plan_options", [])) > 0, f"{mine}")

        # 11. kurum hedefli kampanya
        r = admin.post("/api/v2/admin/campaign-links", json={
            "name": f"{PFX} Kurum Kampanyası", "plan_code": "etut_standart",
            "cycle": "monthly"})
        d2 = r.json() if r.status_code == 200 else {}
        tok2 = d2.get("token")
        check("11a. kurum kampanyası → audience=institution",
              r.status_code == 200 and d2.get("audience") == "institution", f"{r.status_code} {d2}")
        r = anon.post(f"/api/v2/campaign/{tok2}/lead",
                      json={"name": "Kurum Aday", "phone": PH2})
        with SessionLocal() as db:
            pr2 = db.query(SalesProspect).filter(SalesProspect.phone == PH2).first()
            cr2 = db.query(ContactRequest).filter(ContactRequest.phone == PH2).first()
        check("11b. kurum lead → prospect(institution) + hedef_tip=kurum",
              r.status_code == 200 and pr2 is not None and pr2.kind == "institution"
              and cr2 is not None and "hedef_tip=kurum" in (cr2.message or ""),
              f"pr={pr2} msg={cr2.message if cr2 else None}")

        # 12. REGRESYON: campaign_link lead'i admin İletişim Talepleri'nde DOĞRU
        # tanınır → koç lead'i target_kind=coach + tutar + plan (kurum modalına
        # DÜŞMEZ); kurum lead'i target_kind=institution. (Bug: campaign_link parse
        # edilmiyordu → koç lead'i kurum onboarding'ine düşüyordu.)
        r = admin.get("/api/v2/admin/contact-requests")
        items = r.json().get("items", []) if r.status_code == 200 else []
        coach_lead = next((it for it in items if it.get("phone") == PH1
                           and it.get("source") == "campaign_link"), None)
        inst_lead = next((it for it in items if it.get("phone") == PH2
                          and it.get("source") == "campaign_link"), None)
        check("12a. koç kampanya lead → target_kind=coach + tutar=2000 + plan=solo_pro",
              coach_lead is not None and coach_lead.get("target_kind") == "coach"
              and coach_lead.get("requested_amount") == 2000
              and coach_lead.get("requested_plan_code") == "solo_pro",
              f"{coach_lead}")
        check("12b. kurum kampanya lead → target_kind=institution",
              inst_lead is not None and inst_lead.get("target_kind") == "institution",
              f"{inst_lead}")

    finally:
        cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    if failed:
        for f in failed:
            print(f"  FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
