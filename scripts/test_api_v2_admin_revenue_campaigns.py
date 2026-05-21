"""API v2 /admin/revenue/campaigns smoke (D6 P7d).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. campaigns list happy
   4. campaign form meta (7 segment + 7 offer kind)
   5. preview happy (CUSTOM_PLAN + filter → seed kurum)
   6. preview invalid segment → 400
   7. create happy (tek varyant)
   8. create A/B happy
   9. create invalid segment → 400
  10. detail happy (funnel + recipient boş)
  11. detail 404
  12. launch happy (DRAFT → RUNNING + recipient üretir)
  13. launch tekrar → 400 (not_draft)
  14. pause happy
  15. resume happy
  16. complete happy
  17. cancel happy (yeni draft)
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

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    Campaign,
    CampaignRecipient,
    Institution,
    Offer,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adp7d{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassP7d!23"
CUSTOM_PLAN = f"{PFX}pl"

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
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan=CUSTOM_PLAN, is_active=True,
        )
        db.add(inst)
        db.flush()
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()
        out = {"inst_id": inst.id, "super_id": super_admin.id, "teacher_id": teacher.id}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        camp_ids = [c.id for c in db.query(Campaign).filter(Campaign.name.like(f"%{PFX}%")).all()]
        if camp_ids:
            db.execute(sa_delete(CampaignRecipient).where(CampaignRecipient.campaign_id.in_(camp_ids)))
            db.execute(sa_delete(Campaign).where(Campaign.id.in_(camp_ids)))
        db.execute(sa_delete(Offer).where(Offer.institution_id == seed["inst_id"]))
        uids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def _mk_campaign_body(name: str, ab: bool = False) -> dict:
    body = {
        "name": name, "segment": "custom_plan", "filter_plan": CUSTOM_PLAN,
        "variant_a_kind": "discount_percent", "variant_a_title": "%20 indirim",
        "variant_a_value": 20, "variant_a_duration_months": 3,
        "offer_expires_in_days": 14,
    }
    if ab:
        body.update({
            "has_variant_b": True, "variant_b_kind": "trial_extension",
            "variant_b_title": "14 gün ek deneme", "variant_b_value": 14,
        })
    return body


def main() -> int:
    print(f"\n=== API v2 /admin/revenue/campaigns smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    iid = seed["inst_id"]
    print(f"  seeded inst={iid} plan={CUSTOM_PLAN}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. Teacher → 403
        r = tc.get("/api/v2/admin/revenue/campaigns")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get("/api/v2/admin/revenue/campaigns")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. list happy
        r = sc.get("/api/v2/admin/revenue/campaigns")
        check("3. list happy", r.status_code == 200 and "campaigns" in r.json(), f"status={r.status_code}")

        # 4. form meta
        r = sc.get("/api/v2/admin/revenue/campaigns/new")
        j = r.json()
        check("4. form meta", r.status_code == 200 and len(j["segments"]) == 7 and len(j["offer_kinds"]) == 7,
              f"status={r.status_code}")

        # 5. preview happy
        r = sc.post("/api/v2/admin/revenue/campaigns/preview", json={"segment": "custom_plan", "filter_plan": CUSTOM_PLAN})
        j = r.json()
        ok = r.status_code == 200 and j["count"] >= 1 and any(o["owner_id"] == iid for o in j["preview"])
        check("5. preview happy", ok, f"status={r.status_code} count={j.get('count')}")

        # 6. preview invalid segment
        r = sc.post("/api/v2/admin/revenue/campaigns/preview", json={"segment": "not_real"})
        check("6. preview invalid segment → 400", r.status_code == 400
              and r.json().get("detail", {}).get("code") == "invalid_segment", f"status={r.status_code}")

        # 7. create happy
        r = sc.post("/api/v2/admin/revenue/campaigns", json=_mk_campaign_body(f"{PFX} Kampanya A"))
        j = r.json()
        camp_id = j.get("data", {}).get("campaign_id")
        check("7. create happy", r.status_code == 200 and camp_id is not None, f"status={r.status_code} {r.text[:160]}")

        # 8. create A/B
        r = sc.post("/api/v2/admin/revenue/campaigns", json=_mk_campaign_body(f"{PFX} Kampanya AB", ab=True))
        camp_ab = r.json().get("data", {}).get("campaign_id")
        check("8. create A/B", r.status_code == 200 and camp_ab is not None, f"status={r.status_code}")

        # 9. create invalid segment
        r = sc.post("/api/v2/admin/revenue/campaigns", json={
            "name": f"{PFX} bad", "segment": "not_real",
            "variant_a_kind": "discount_percent", "variant_a_title": "x",
        })
        check("9. create invalid segment → 400", r.status_code == 400
              and r.json().get("detail", {}).get("code") == "campaign_invalid", f"status={r.status_code}")

        # 10. detail happy (DRAFT — recipient boş)
        r = sc.get(f"/api/v2/admin/revenue/campaigns/{camp_id}")
        j = r.json()
        ok = (r.status_code == 200 and j["campaign"]["id"] == camp_id
              and "stats" in j and "recipients" in j and j["stats"]["overall"]["total"] == 0)
        check("10. detail happy", ok, f"status={r.status_code}")

        # 11. detail 404
        r = sc.get("/api/v2/admin/revenue/campaigns/999999")
        check("11. detail 404", r.status_code == 404
              and r.json().get("detail", {}).get("code") == "campaign_not_found", f"status={r.status_code}")

        # 12. launch happy
        r = sc.post(f"/api/v2/admin/revenue/campaigns/{camp_id}/launch")
        j = r.json()
        ok = r.status_code == 200 and (j.get("data", {}).get("recipient_count") or 0) >= 1
        check("12. launch happy", ok, f"status={r.status_code} {r.text[:160]}")

        # 13. launch tekrar → 400
        r = sc.post(f"/api/v2/admin/revenue/campaigns/{camp_id}/launch")
        check("13. launch tekrar → 400", r.status_code == 400, f"status={r.status_code}")

        # 14. pause
        r = sc.post(f"/api/v2/admin/revenue/campaigns/{camp_id}/pause")
        check("14. pause happy", r.status_code == 200 and "duraklatıldı" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

        # 15. resume
        r = sc.post(f"/api/v2/admin/revenue/campaigns/{camp_id}/resume")
        check("15. resume happy", r.status_code == 200 and "devam" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

        # 16. complete
        r = sc.post(f"/api/v2/admin/revenue/campaigns/{camp_id}/complete")
        check("16. complete happy", r.status_code == 200 and "tamamlandı" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

        # 17. cancel (camp_ab hâlâ draft)
        r = sc.post(f"/api/v2/admin/revenue/campaigns/{camp_ab}/cancel")
        check("17. cancel happy", r.status_code == 200 and "iptal" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
