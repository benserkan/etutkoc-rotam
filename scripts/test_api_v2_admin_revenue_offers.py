"""API v2 /admin/revenue offers + action-templates + invoices smoke (D6 P7c).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. action-templates list happy (templates + kinds)
   4. action-template create happy
   5. action-template create geçersiz kind → 400
   6. action-template update happy
   7. action-template render happy (owner bağlamında)
   8. action-template delete happy
   9. offer create (institution) happy
  10. offer create geçersiz kind → 400
  11. offer send happy
  12. offer cancel happy
  13. institution 360 GET → offers içeriyor
  14. invoice postpone happy
  15. invoice mark-paid happy
  16. invoice cancel happy
  17. invoice send-reminder happy (user invoice — email var)
  18. institution 360 GET → invoices içeriyor
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    CrmActionTemplate,
    Institution,
    Invoice,
    InvoiceStatus,
    Offer,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adp7c{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassP7c!23"

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


def _mk_invoice(db, *, owner_type, owner_id, status, due_offset_days):
    now = datetime.now(timezone.utc)
    kw = {"owner_type": owner_type,
          "institution_id": owner_id if owner_type == "institution" else None,
          "user_id": owner_id if owner_type == "user" else None}
    inv = Invoice(
        plan="kurumsal_pro", amount_try=2999, status=status,
        period_start=now - timedelta(days=30), period_end=now,
        due_at=now + timedelta(days=due_offset_days), **kw,
    )
    db.add(inv)
    db.flush()
    return inv.id


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="kurumsal_pro", is_active=True,
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
            role=UserRole.TEACHER, institution_id=None, is_active=True, plan="pro_solo",
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()
        out = {
            "inst_id": inst.id, "super_id": super_admin.id, "teacher_id": teacher.id,
            "inv_postpone": _mk_invoice(db, owner_type="institution", owner_id=inst.id, status=InvoiceStatus.PENDING, due_offset_days=5),
            "inv_markpaid": _mk_invoice(db, owner_type="institution", owner_id=inst.id, status=InvoiceStatus.PENDING, due_offset_days=5),
            "inv_cancel": _mk_invoice(db, owner_type="institution", owner_id=inst.id, status=InvoiceStatus.PENDING, due_offset_days=5),
            "inv_reminder": _mk_invoice(db, owner_type="user", owner_id=teacher.id, status=InvoiceStatus.OVERDUE, due_offset_days=-5),
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(Invoice).where(
            (Invoice.institution_id == seed["inst_id"]) | (Invoice.user_id.in_(uids))
        ))
        db.execute(sa_delete(Offer).where(
            (Offer.institution_id == seed["inst_id"]) | (Offer.user_id.in_(uids))
        ))
        db.execute(sa_delete(CrmActionTemplate).where(CrmActionTemplate.name.like(f"%{PFX}%")))
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


def main() -> int:
    print(f"\n=== API v2 /admin/revenue offers+templates+invoices smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    iid, tid = seed["inst_id"], seed["teacher_id"]
    print(f"  seeded inst={iid} teacher={tid}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. Teacher → 403
        r = tc.get("/api/v2/admin/revenue/action-templates")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get("/api/v2/admin/revenue/action-templates")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. action-templates list
        r = sc.get("/api/v2/admin/revenue/action-templates")
        j = r.json()
        check("3. templates list", r.status_code == 200 and "templates" in j and len(j["kinds"]) == 7,
              f"status={r.status_code}")

        # 4. template create
        r = sc.post("/api/v2/admin/revenue/action-templates", json={
            "name": f"{PFX} Trial uyarı", "kind": "email",
            "subject": "Deneme bitiyor", "body": "Merhaba {{owner_name}}, plan: {{plan}}",
            "description": "trial son",
        })
        j = r.json()
        tpl_id = j.get("data", {}).get("template_id")
        check("4. template create", r.status_code == 200 and tpl_id is not None, f"status={r.status_code} {r.text[:160]}")

        # 5. template create invalid kind
        r = sc.post("/api/v2/admin/revenue/action-templates", json={
            "name": f"{PFX} bad", "kind": "not_real", "body": "x",
        })
        check("5. template invalid kind → 400", r.status_code == 400
              and r.json().get("detail", {}).get("code") == "template_invalid", f"status={r.status_code}")

        # 6. template update
        r = sc.post(f"/api/v2/admin/revenue/action-templates/{tpl_id}", json={
            "name": f"{PFX} Trial uyarı v2", "kind": "email", "body": "Güncel {{owner_name}}", "is_active": True,
        })
        check("6. template update", r.status_code == 200, f"status={r.status_code}")

        # 7. template render (owner bağlamında)
        r = sc.get(f"/api/v2/admin/revenue/action-templates/{tpl_id}/render?owner_type=institution&owner_id={iid}")
        j = r.json()
        ok = r.status_code == 200 and j.get("ok") and f"{PFX} Inst" in j.get("body", "")
        check("7. template render", ok, f"status={r.status_code} {r.text[:160]}")

        # 8. template delete
        r = sc.post(f"/api/v2/admin/revenue/action-templates/{tpl_id}/delete")
        check("8. template delete", r.status_code == 200, f"status={r.status_code}")

        # 9. offer create (institution)
        r = sc.post(f"/api/v2/admin/revenue/institution/{iid}/offers", json={
            "kind": "discount_percent", "title": "3 ay %20", "value": 20,
            "duration_months": 3, "expires_in_days": 14, "send_now": False,
        })
        j = r.json()
        offer_id = j.get("data", {}).get("offer_id")
        check("9. offer create", r.status_code == 200 and offer_id is not None, f"status={r.status_code} {r.text[:160]}")

        # 10. offer create invalid kind
        r = sc.post(f"/api/v2/admin/revenue/institution/{iid}/offers", json={
            "kind": "not_real", "title": "x",
        })
        check("10. offer invalid kind → 400", r.status_code == 400
              and r.json().get("detail", {}).get("code") == "invalid_offer_kind", f"status={r.status_code}")

        # 11. offer send
        r = sc.post(f"/api/v2/admin/revenue/offers/{offer_id}/send")
        check("11. offer send", r.status_code == 200 and "gönderildi" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

        # 12. offer cancel (yeni draft)
        r = sc.post(f"/api/v2/admin/revenue/institution/{iid}/offers", json={
            "kind": "trial_extension", "title": "14 gün ek", "value": 14,
        })
        offer2 = r.json()["data"]["offer_id"]
        r = sc.post(f"/api/v2/admin/revenue/offers/{offer2}/cancel")
        check("12. offer cancel", r.status_code == 200 and "iptal" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

        # 13. 360 GET offers içeriyor
        r = sc.get(f"/api/v2/admin/revenue/institutions/{iid}")
        j = r.json()
        ok = r.status_code == 200 and "offers" in j and len(j["offers"]) >= 2 and len(j["meta"]["offer_kinds"]) == 7
        check("13. 360 offers + meta.offer_kinds", ok, f"status={r.status_code}")

        # 14. invoice postpone
        r = sc.post(f"/api/v2/admin/revenue/invoices/{seed['inv_postpone']}/postpone", json={"days": 7, "note": "tatil"})
        check("14. invoice postpone", r.status_code == 200 and "ileri" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

        # 15. invoice mark-paid
        r = sc.post(f"/api/v2/admin/revenue/invoices/{seed['inv_markpaid']}/mark-paid", json={"method": "bank_transfer", "note": "havale"})
        check("15. invoice mark-paid", r.status_code == 200 and "ödenmiş" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")
        # tekrar mark-paid → 400 already
        r = sc.post(f"/api/v2/admin/revenue/invoices/{seed['inv_markpaid']}/mark-paid", json={})
        check("15b. mark-paid tekrar → 400", r.status_code == 400
              and r.json().get("detail", {}).get("code") == "invoice_already_paid", f"status={r.status_code}")

        # 16. invoice cancel
        r = sc.post(f"/api/v2/admin/revenue/invoices/{seed['inv_cancel']}/cancel", json={"note": "çift kayıt"})
        check("16. invoice cancel", r.status_code == 200 and "iptal" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code}")

        # 17. invoice send-reminder (user invoice — email var)
        r = sc.post(f"/api/v2/admin/revenue/invoices/{seed['inv_reminder']}/send-reminder", json={"kind": "manual"})
        check("17. invoice send-reminder", r.status_code == 200 and "Hatırlatma" in r.json().get("data", {}).get("message", ""),
              f"status={r.status_code} {r.text[:160]}")

        # 18. 360 GET invoices içeriyor
        r = sc.get(f"/api/v2/admin/revenue/institutions/{iid}")
        j = r.json()
        ok = r.status_code == 200 and "invoices" in j and len(j["invoices"]) >= 3
        check("18. 360 invoices", ok, f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
