"""K2 — Cloud API branded üyelik teklifi gönderimi (send-whatsapp) smoke.

whatsapp.send_template + is_enabled monkeypatch'li (gerçek Meta çağrısı YOK).

Senaryolar:
  1. teacher (admin değil) → 403
  2. WhatsApp kapalıyken → 409 whatsapp_disabled
  3. telefonsuz hedef → 422 no_phone
  4. happy: gönder → 200 + wa_sent_at + offer.wa_sent_at/wa_message_id + comm_log(sent)
  5. gönderim hatası (send_template success=False) → 502 wa_send_failed + comm_log(failed)
  6. apply_whatsapp_event: delivered → comm_log sent'i delivered'a yükseltir; failed → failed
  7. liste yanıtı whatsapp_enabled=true + item.wa_sent
  8. olmayan teklif → 404
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
from app.models import CommunicationLog, MembershipOffer, User, UserRole
from app.models.communication_log import CHANNEL_WHATSAPP, STATUS_DELIVERED, STATUS_FAILED, STATUS_SENT
from app.config import settings
from app.services import whatsapp, comm_log
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.models.suspicious_ip import SuspiciousIp

PFX = f"k2wa_{secrets.token_hex(3)}"
PWD = hash_password("K2wa!23")
PWDH = "K2wa!23"
PHONE = "905388880077"
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
        db.execute(sa_delete(CommunicationLog).where(CommunicationLog.to_address == PHONE))
        db.query(MembershipOffer).filter(MembershipOffer.token.like(f"{PFX}%")).delete(
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
                     must_change_password=False, phone=PHONE)
        nophone = User(email=f"{PFX}_np@test.invalid", password_hash=PWD,
                       full_name=f"{PFX} Telefonsuz", role=UserRole.TEACHER, institution_id=None,
                       is_active=True, plan="solo_free", password_changed_at=now,
                       must_change_password=False)
        db.add_all([admin, coach, nophone]); db.flush()
        o = MembershipOffer(token=f"{PFX}_{secrets.token_hex(6)}", created_by_admin_id=admin.id,
                            target_user_id=coach.id, offer_type="new", plan_code="solo_pro",
                            cycle="monthly", amount=2000, status="active")
        o2 = MembershipOffer(token=f"{PFX}_{secrets.token_hex(6)}", created_by_admin_id=admin.id,
                             target_user_id=nophone.id, offer_type="new", plan_code="solo_pro",
                             cycle="monthly", amount=2000, status="active")
        db.add_all([o, o2]); db.commit()
        ctx.update(admin=admin.id, offer=o.id, offer_nophone=o2.id)


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code} {r.text[:120]}")
    return c


def main() -> int:
    print(f"\n=== K2 WHATSAPP CLOUD API GÖNDERİM — {PFX} ===\n")
    setup()
    oid = ctx["offer"]

    # monkeypatch — gerçek Meta çağrısı yapma
    orig_send = whatsapp.send_template
    orig_enabled = whatsapp.is_enabled
    orig_btn = settings.whatsapp_offer_button_dynamic
    settings.whatsapp_offer_button_dynamic = True  # buton param yapısını test et
    sent_payloads: list = []

    def fake_send(*, to_phone, template_name, components=None, language_code=None):
        sent_payloads.append({"to": to_phone, "tpl": template_name, "comp": components})
        return whatsapp.WhatsAppResult(success=True, external_id="wamid.TESTK2")

    try:
        admin = login("admin")
        coach = login("coach")

        # 1. teacher → 403
        r = coach.post(f"/api/v2/admin/membership-offers/{oid}/send-whatsapp")
        check("1. teacher → 403", r.status_code == 403, f"{r.status_code}")

        # 2. WhatsApp kapalı → 409 (is_enabled gerçek = False)
        whatsapp.is_enabled = lambda: False
        r = admin.post(f"/api/v2/admin/membership-offers/{oid}/send-whatsapp")
        check("2. kapalı → 409 whatsapp_disabled",
              r.status_code == 409 and _code(r) == "whatsapp_disabled", f"{r.status_code} {_code(r)}")

        # Aç (monkeypatch)
        whatsapp.is_enabled = lambda: True
        whatsapp.send_template = fake_send

        # 3. telefonsuz hedef → 422 no_phone
        r = admin.post(f"/api/v2/admin/membership-offers/{ctx['offer_nophone']}/send-whatsapp")
        check("3. telefonsuz → 422 no_phone",
              r.status_code == 422 and _code(r) == "no_phone", f"{r.status_code} {_code(r)}")

        # 4. happy
        r = admin.post(f"/api/v2/admin/membership-offers/{oid}/send-whatsapp")
        ok = r.status_code == 200 and r.json().get("ok") is True
        check("4. gönder → 200 ok + wa_sent_at", ok and r.json().get("wa_sent_at"),
              f"{r.status_code} {r.text[:160]}")
        with SessionLocal() as db:
            o = db.get(MembershipOffer, oid)
            cl = db.query(CommunicationLog).filter(
                CommunicationLog.to_address == PHONE,
                CommunicationLog.channel == CHANNEL_WHATSAPP).order_by(
                CommunicationLog.id.desc()).first()
            check("4b. offer.wa_sent_at + wa_message_id set",
                  o.wa_sent_at is not None and o.wa_message_id == "wamid.TESTK2", f"{o.wa_message_id}")
            check("4c. comm_log whatsapp(sent) + provider_message_id",
                  cl is not None and cl.status == STATUS_SENT and cl.provider_message_id == "wamid.TESTK2"
                  and cl.category == "membership_offer", f"{cl}")
        # payload: doğru şablon + 3 body param + buton token
        p = sent_payloads[-1]
        comp = p["comp"] or []
        body = next((c for c in comp if c["type"] == "body"), {})
        btn = next((c for c in comp if c["type"] == "button"), {})
        check("4d. payload şablon=uyelik_teklifi + header+body(3)+button(token)",
              p["tpl"] == "uyelik_teklifi" and len(body.get("parameters", [])) == 3
              and btn.get("parameters", [{}])[0].get("text", "").startswith(PFX),
              f"tpl={p['tpl']} body={len(body.get('parameters',[]))}")

        # 5. gönderim hatası
        whatsapp.send_template = lambda **kw: whatsapp.WhatsAppResult(success=False, error="http_131000")
        # yeni teklif (oid zaten gönderildi — accepted değil, tekrar gönderilebilir ama temiz olsun)
        with SessionLocal() as db:
            o3 = MembershipOffer(token=f"{PFX}_{secrets.token_hex(6)}", created_by_admin_id=ctx["admin"],
                                 target_user_id=db.get(MembershipOffer, oid).target_user_id,
                                 offer_type="new", plan_code="solo_pro", cycle="monthly",
                                 amount=2000, status="active")
            db.add(o3); db.commit(); o3id = o3.id
        r = admin.post(f"/api/v2/admin/membership-offers/{o3id}/send-whatsapp")
        check("5. gönderim hatası → 502 wa_send_failed",
              r.status_code == 502 and _code(r) == "wa_send_failed", f"{r.status_code} {_code(r)}")
        with SessionLocal() as db:
            clf = db.query(CommunicationLog).filter(
                CommunicationLog.to_address == PHONE, CommunicationLog.status == STATUS_FAILED,
                CommunicationLog.channel == CHANNEL_WHATSAPP).first()
            check("5b. comm_log whatsapp(failed) yazıldı", clf is not None, "")

        # 6. apply_whatsapp_event: delivered yükseltir
        n = comm_log.apply_whatsapp_event("wamid.TESTK2", "delivered")
        with SessionLocal() as db:
            cl = db.query(CommunicationLog).filter(
                CommunicationLog.provider_message_id == "wamid.TESTK2").first()
            check("6. delivered event → comm_log delivered",
                  n == 1 and cl.status == STATUS_DELIVERED, f"n={n} status={cl.status if cl else None}")
        n2 = comm_log.apply_whatsapp_event("wamid.TESTK2", "sent")
        check("6b. sent (daha düşük) → güncelleme yok", n2 == 0, f"n2={n2}")

        # 7. liste
        r = admin.get("/api/v2/admin/membership-offers")
        j = r.json()
        item = next((x for x in j.get("items", []) if x["id"] == oid), None)
        check("7. liste whatsapp_enabled=true + item.wa_sent",
              j.get("whatsapp_enabled") is True and item is not None and item["wa_sent"] is True,
              f"enabled={j.get('whatsapp_enabled')} item={item}")

        # 8. olmayan teklif
        r = admin.post("/api/v2/admin/membership-offers/99999999/send-whatsapp")
        check("8. olmayan teklif → 404",
              r.status_code == 404 and _code(r) == "offer_not_found", f"{r.status_code} {_code(r)}")

    finally:
        whatsapp.send_template = orig_send
        whatsapp.is_enabled = orig_enabled
        settings.whatsapp_offer_button_dynamic = orig_btn
        cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
